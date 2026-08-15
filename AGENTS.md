# Kryten-Robot — Project Guidelines

Kryten-Robot is the **CyTube ↔ NATS bridge** and the ecosystem's foundation service. It connects to CyTube over Socket.IO, is the **sole publisher of CyTube events** to NATS, and **owns the channel state KV buckets** (playlist, userlist, emotes) that every other service reads. Its behavior defines contracts the whole ecosystem depends on.

## Architecture
- **Sole event publisher.** Kryten-Robot publishes all CyTube events on `kryten.events.{domain}.{channel}.{event_type}` (normalized: lowercase, dots stripped). No other service publishes these — changing an event's shape or subject is an ecosystem-wide breaking change.
- **Owns channel state.** Creates and writes channel KV buckets (`kryten_{channel}_{type}`) via `get_or_create_kv_store`; all other services bind them read-only. Guard this write path carefully.
- Handle control commands on the single subject `kryten.robot.command` (e.g. `say`, `pm`, `restart`, `halt`, `system.ping`, `system.stats`), dispatching on the `command` field and replying `{"service","command","success",...}`.
- Use the shared **`kryten-py`** library (`KrytenClient`) for NATS, lifecycle, health, and KV — do not use raw `nats-py`. Ecosystem contracts: [../KRYTEN_ARCHITECTURE.md](../KRYTEN_ARCHITECTURE.md), [../kryten-py/COMMAND_PROTOCOL.md](../kryten-py/COMMAND_PROTOCOL.md), [../kryten-py/STATE_MANAGEMENT.md](../kryten-py/STATE_MANAGEMENT.md).
- **Note:** the importable package is `kryten` (root-level), the same top-level name as the kryten-py library. Keep this repo's `kryten` package (the robot app) distinct from the installed `kryten` library dependency; don't confuse or shadow them.

## Build, Test & Conventions
Shared ecosystem rules (uv build/test, config auto-discovery, versioning, commit
style, NATS/KV patterns, contract-change policy): see
[../KRYTEN_CONVENTIONS.md](../KRYTEN_CONVENTIONS.md). Repo specifics:
- **Python 3.10+**; mypy target `uv run mypy kryten` (the robot app package,
  distinct from the installed `kryten` library — don't shadow them).
- Config: `/etc/kryten/kryten-robot/config.json` (JSON auto-discovery). Multiple
  channel configs exist (e.g. `config-420grindhouse.json`, `config.idle.json`) —
  keep them consistent with the schema.
- **Event handlers and the Socket.IO bridge must catch and log exceptions**;
  handle CyTube disconnects gracefully without dropping event publication.
- Event shape, subject naming, KV bucket schema, and `kryten.robot.command` are
  the **highest-stakes** surface in the ecosystem (sole event publisher; owns
  channel state) — keep backward compatible and version/document any break.
