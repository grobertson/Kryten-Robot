#!/usr/bin/env python3
"""Test script for system query commands (Phase 2).

Tests the three new query commands:
- system.stats
- system.config
- system.ping

Requires a running Kryten-Robot instance and NATS server.
"""

import asyncio
import json
import sys
from datetime import datetime
from typing import Any

try:
    from nats.aio.client import Client as NATS
except ImportError:
    print("ERROR: nats-py not installed")
    print("Install with: pip install nats-py")
    sys.exit(1)


async def send_command(nc: NATS, command: str, **kwargs) -> dict[str, Any]:
    """Send a command via NATS request-reply and return the response.

    Args:
        nc: Connected NATS client
        command: Command name (e.g., "system.stats")
        **kwargs: Additional parameters for the command

    Returns:
        Response dictionary
    """
    request = {"service": "robot", "command": command, **kwargs}

    subject = "kryten.robot.command"

    try:
        response = await nc.request(subject, json.dumps(request).encode(), timeout=5.0)
        return json.loads(response.data.decode())  # type: ignore
    except TimeoutError:
        return {"error": "Timeout waiting for response", "success": False}
    except Exception as e:
        return {"error": str(e), "success": False}


def print_section(title: str):
    """Print a formatted section header."""
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}\n")


def format_timestamp(iso_str: str | None) -> str:
    """Format ISO timestamp for display."""
    if not iso_str:
        return "N/A"
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        return iso_str


def format_uptime(seconds: float) -> str:
    """Format uptime seconds as human-readable."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        return f"{seconds / 60:.1f}m"
    elif seconds < 86400:
        return f"{seconds / 3600:.1f}h"
    else:
        days = int(seconds / 86400)
        hours = (seconds % 86400) / 3600
        return f"{days}d {hours:.1f}h"


async def test_system_ping(nc: NATS):
    """Test system.ping command."""
    print_section("Testing system.ping")

    response = await send_command(nc, "system.ping")

    if not response.get("success"):
        print(f"❌ FAILED: {response.get('error', 'Unknown error')}")
        return False

    data = response.get("data", {})

    print("✅ PASSED: system.ping")
    print(f"  Pong:      {data.get('pong')}")
    print(f"  Service:   {data.get('service')}")
    print(f"  Version:   {data.get('version')}")
    print(f"  Uptime:    {format_uptime(data.get('uptime_seconds', 0))}")
    print(f"  Timestamp: {format_timestamp(data.get('timestamp'))}")

    return True


async def test_system_config(nc: NATS):
    """Test system.config command."""
    print_section("Testing system.config")

    response = await send_command(nc, "system.config")

    if not response.get("success"):
        print(f"❌ FAILED: {response.get('error', 'Unknown error')}")
        return False

    data = response.get("data", {})

    print("✅ PASSED: system.config")

    # Check CyTube config
    cytube = data.get("cytube", {})
    print("\nCyTube:")
    print(f"  Domain:   {cytube.get('domain')}")
    print(f"  Channel:  {cytube.get('channel')}")
    print(f"  User:     {cytube.get('user')}")
    print(f"  Password: {cytube.get('password')} (should be ***REDACTED***)")

    # Verify password redaction
    if cytube.get("password") != "***REDACTED***":
        print("  ⚠️  WARNING: Password not properly redacted!")

    # Check NATS config
    nats_config = data.get("nats", {})
    print("\nNATS:")
    print(f"  Servers:  {', '.join(nats_config.get('servers', []))}")
    print(f"  User:     {nats_config.get('user')}")
    print(f"  Password: {nats_config.get('password')} (should be None or ***REDACTED***)")

    # Check other sections
    health = data.get("health", {})
    print("\nHealth:")
    print(f"  Enabled:  {health.get('enabled')}")
    print(f"  Host:     {health.get('host')}")
    print(f"  Port:     {health.get('port')}")

    commands = data.get("commands", {})
    print("\nCommands:")
    print(f"  Enabled:  {commands.get('enabled')}")

    print("\nLogging:")
    print(f"  Level:    {data.get('log_level')}")

    return True


async def test_system_stats(nc: NATS):
    """Test system.stats command."""
    print_section("Testing system.stats")

    response = await send_command(nc, "system.stats")

    if not response.get("success"):
        print(f"❌ FAILED: {response.get('error', 'Unknown error')}")
        return False

    data = response.get("data", {})

    print("✅ PASSED: system.stats")

    # Overall uptime
    uptime = data.get("uptime_seconds", 0)
    print(f"\nUptime: {format_uptime(uptime)} ({uptime:.1f}s)")

    # Events
    events = data.get("events", {})
    print("\nEvents:")
    print(f"  Published:     {events.get('published', 0):,}")
    print(f"  Failed:        {events.get('failed', 0):,}")
    print(f"  Rate (1m):     {events.get('rate_1min', 0):.2f}/sec")
    print(f"  Rate (5m):     {events.get('rate_5min', 0):.2f}/sec")
    last_event_time = events.get("last_event_time")
    if last_event_time:
        print(
            f"  Last Event:    {events.get('last_event_type')} at {format_timestamp(last_event_time)}"
        )

    # Commands
    commands = data.get("commands", {})
    print("\nCommands:")
    print(f"  Received:      {commands.get('received', 0):,}")
    print(f"  Executed:      {commands.get('executed', 0):,}")
    print(f"  Failed:        {commands.get('failed', 0):,}")
    print(f"  Rate (1m):     {commands.get('rate_1min', 0):.2f}/sec")
    last_cmd_time = commands.get("last_command_time")
    if last_cmd_time:
        print(
            f"  Last Command:  {commands.get('last_command_type')} at {format_timestamp(last_cmd_time)}"
        )

    # Queries
    queries = data.get("queries", {})
    print("\nQueries:")
    print(f"  Processed:     {queries.get('processed', 0):,}")
    print(f"  Failed:        {queries.get('failed', 0):,}")
    print(f"  Rate (1m):     {queries.get('rate_1min', 0):.2f}/sec")

    # Connections
    connections = data.get("connections", {})

    cytube = connections.get("cytube", {})
    print("\nCyTube Connection:")
    print(f"  Connected:     {'✓' if cytube.get('connected') else '✗'}")
    print(f"  Uptime:        {format_uptime(cytube.get('uptime_seconds', 0))}")
    print(f"  Reconnects:    {cytube.get('reconnect_count', 0)}")
    last_event = cytube.get("last_event_time")
    if last_event:
        print(f"  Last Event:    {format_timestamp(last_event)}")

    nats_conn = connections.get("nats", {})
    print("\nNATS Connection:")
    print(f"  Connected:     {'✓' if nats_conn.get('connected') else '✗'}")
    print(f"  Server:        {nats_conn.get('server', 'N/A')}")
    print(f"  Uptime:        {format_uptime(nats_conn.get('uptime_seconds', 0))}")
    print(f"  Reconnects:    {nats_conn.get('reconnect_count', 0)}")

    # State
    state = data.get("state", {})
    print("\nChannel State:")
    print(f"  Users Online:  {state.get('users_online', 0)}")
    print(f"  Playlist:      {state.get('playlist_items', 0)} items")
    print(f"  Emotes:        {state.get('emotes_count', 0)}")

    # Memory
    memory = data.get("memory", {})
    print("\nMemory:")
    if "error" in memory:
        print(f"  Error:         {memory.get('error')}")
    else:
        print(f"  RSS:           {memory.get('rss_mb', 0):.1f} MB")
        print(f"  VMS:           {memory.get('vms_mb', 0):.1f} MB")

    return True


async def main():
    """Run all tests."""
    print("=" * 70)
    print("  System Query Commands Test Suite (Phase 2)")
    print("=" * 70)
    print("\nConnecting to NATS...")

    # Connect to NATS
    nc = NATS()

    try:
        await nc.connect("nats://localhost:4222")
        print("✓ Connected to NATS")
    except Exception as e:
        print(f"✗ Failed to connect to NATS: {e}")
        print("\nMake sure:")
        print("  1. NATS server is running (nats-server)")
        print("  2. Kryten-Robot is running with config.json")
        return 1

    # Run tests
    results = []

    try:
        # Test 1: ping (lightweight, fast)
        results.append(await test_system_ping(nc))

        # Test 2: config
        results.append(await test_system_config(nc))

        # Test 3: stats (comprehensive)
        results.append(await test_system_stats(nc))

    except Exception as e:
        print(f"\n❌ Test suite failed with exception: {e}")
        import traceback

        traceback.print_exc()
        return 1
    finally:
        await nc.close()

    # Summary
    print_section("Test Summary")

    passed = sum(results)
    total = len(results)

    print(f"Tests Passed: {passed}/{total}")

    if passed == total:
        print("\n✅ All tests PASSED!")
        return 0
    else:
        print(f"\n❌ {total - passed} test(s) FAILED")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
