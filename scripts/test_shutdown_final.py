#!/usr/bin/env python3
"""Test system.shutdown with 10 second delay after fixing shutdown_event bug."""

import asyncio
import json
import sys
from datetime import datetime

from nats.aio.client import Client as NATS


async def test_shutdown():
    """Test shutdown command with 10 second delay."""
    nc = NATS()

    try:
        # Connect to NATS
        await nc.connect("nats://localhost:4222")
        print("✅ Connected to NATS")

        # Send shutdown command with 10 second delay using unified command pattern
        request = {
            "service": "robot",
            "command": "system.shutdown",
            "delay_seconds": 10,
            "reason": "Integration test - shutdown_event fix validation",
        }

        print("\n📤 Sending system.shutdown command:")
        print("   Subject: kryten.robot.command")
        print(f"   Delay: {request['delay_seconds']} seconds")
        print(f"   Reason: {request['reason']}")
        print(f"   Current time: {datetime.now().strftime('%H:%M:%S')}")

        response = await nc.request(
            "kryten.robot.command", json.dumps(request).encode(), timeout=5.0
        )

        response_data = json.loads(response.data.decode())
        result = response_data.get("data", {})

        if response_data.get("success") and result.get("success"):
            print("\n✅ Shutdown command ACCEPTED:")
            print(f"   Success:       {result['success']}")
            print(f"   Message:       {result['message']}")
            print(f"   Delay:         {result['delay_seconds']} seconds")
            print(f"   Shutdown time: {result['shutdown_time']}")
            print(f"   Reason:        {result['reason']}")
            print(f"\n⚠️  Kryten-Robot WILL shut down in {result['delay_seconds']} seconds!")
            print(f"   Expected shutdown: ~{datetime.now().strftime('%H:%M:%S')} + 10s")
        else:
            print("\n❌ Shutdown command REJECTED:")
            print(f"   Response: {response_data}")
            print(f"   Error: {result.get('error', 'Unknown error')}")
            sys.exit(1)

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        sys.exit(1)
    finally:
        await nc.close()


if __name__ == "__main__":
    asyncio.run(test_shutdown())
