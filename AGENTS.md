# Kryten-Robot — Project Guidelines

Kryten-Robot is the **CyTube ↔ NATS bridge** and the ecosystem's foundation service. It connects to CyTube over Socket.IO, is the **sole publisher of CyTube events** to NATS, and **owns the channel state KV buckets** (playlist, userlist, emotes) that every other service reads. Its behavior defines contracts the whole ecosystem depends on.

## Architecture
- **Sole event publisher.** Kryten-Robot publishes all CyTube events on `kryten.events.{domain}.{channel}.{event_type}` (normalized: lowercase, dots stripped). No other service publishes these — changing an event's shape or subject is an ecosystem-wide breaking change.
- **Owns channel state.** Creates and writes channel KV buckets (`kryten_{channel}_{type}`) via `get_or_create_kv_store`; all other services bind them read-only. Guard this write path carefully.
- Handle control commands on the single subject `kryten.robot.command` (e.g. `say`, `pm`, `restart`, `halt`, `system.ping`, `system.stats`), dispatching on the `command` field and replying `{"service","command","success",...}`.
- Use the shared **`kryten-py`** library (`KrytenClient`) for NATS, lifecycle, health, and KV — do not use raw `nats-py`. Ecosystem contracts: [../KRYTEN_ARCHITECTURE.md](../KRYTEN_ARCHITECTURE.md), [../kryten-py/COMMAND_PROTOCOL.md](../kryten-py/COMMAND_PROTOCOL.md), [../kryten-py/STATE_MANAGEMENT.md](../kryten-py/STATE_MANAGEMENT.md).
- **Note:** the importable package is `kryten` (root-level), the same top-level name as the kryten-py library. Keep this repo's `kryten` package (the robot app) distinct from the installed `kryten` library dependency; don't confuse or shadow them.

## Build and Test
Run from the repo root (uv-managed):
- Install deps: `uv sync`
- Format: `uv run black .`
- Lint (autofix): `uv run ruff check --fix .`
- Types: `uv run mypy kryten`
- Tests: `uv run pytest`

Run all four before committing. Do not bypass checks (`--no-verify`).

## Conventions
- Python 3.10+, 100% `async`/`await`, Pydantic v2 config. black/ruff `line-length = 100` (E501 ignored). pytest `asyncio_mode = "auto"`.
- **Event handlers and the Socket.IO bridge must catch and log exceptions — never raise into the event loop.** Rely on `kryten-py` auto-reconnect for NATS; handle CyTube disconnects gracefully without dropping event publication.
- Config is JSON with auto-discovery: `--config` flag → `/etc/kryten/kryten-robot/config.json` → `./config.json`. Keep `config.example.json` in sync; never hardcode values or NATS subjects. Multiple channel configs exist (e.g. `config-420grindhouse.json`, `config.idle.json`) — keep them consistent with the schema.
- Event shape, subject naming, KV bucket schema, and `kryten.robot.command` contracts are the highest-stakes surface in the ecosystem: flag changes, keep backward compatibility, and version/document any break.
- Version lives only in `pyproject.toml [project] version`. Update `CHANGELOG.md` (Keep-a-Changelog + SemVer, ISO dates) for versioned changes.
- Commit prefixes: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`, `ci:`. Branches: `feature/…`, `fix/…`.
