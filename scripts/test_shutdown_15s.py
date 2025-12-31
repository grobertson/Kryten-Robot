#!/usr/bin/env python3
"""Test system.shutdown with 15 second delay."""

import asyncio
import json
from datetime import datetime


async def test():
    try:
        from nats.aio.client import Client as NATS
    except ImportError:
        print("❌ nats-py not installed")
        return

    nc = NATS()

    try:
        await nc.connect("nats://localhost:4222")
        print("✓ Connected to NATS\n")
    except Exception as e:
        print(f"❌ Failed to connect to NATS: {e}")
        return

    print("=" * 70)
    print("Testing system.shutdown with 15 second delay")
    print("=" * 70)
    print()

    # Test system.shutdown with 15 second delay
    request = {
        "service": "robot",
        "command": "system.shutdown",
        "delay_seconds": 15,
        "reason": "Integration test - 15 second delay",
    }

    try:
        print(f"Sending shutdown request at {datetime.now().strftime('%H:%M:%S')}...")
        response = await nc.request(
            "kryten.robot.command", json.dumps(request).encode(), timeout=5.0
        )
        data = json.loads(response.data.decode())

        if data.get("success"):
            result = data["data"]
            print("\n✅ Shutdown command ACCEPTED:\n")
            print(f"   Success:       {result.get('success', True)}")
            print(f"   Message:       {result['message']}")
            print(f"   Delay:         {result['delay_seconds']} seconds")
            print(f"   Shutdown time: {result['shutdown_time']}")
            print(f"   Reason:        {result['reason']}")
            print("\n⚠️  Kryten-Robot WILL shut down in 15 seconds!")
            print(f"   Current time: {datetime.now().strftime('%H:%M:%S')}")

            # Parse shutdown time
            try:
                shutdown_dt = datetime.fromisoformat(result["shutdown_time"].replace("Z", "+00:00"))
                print(f"   Expected shutdown: {shutdown_dt.strftime('%H:%M:%S')}")
            except Exception:
                pass

        else:
            print("\n❌ Shutdown command REJECTED:")
            print(f"   Error: {data.get('error')}")
            return

    except TimeoutError:
        print("❌ Timeout waiting for response")
        return
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
        return

    await nc.close()

    print("\nTest completed. Monitor Kryten-Robot logs for shutdown sequence.")


if __name__ == "__main__":
    asyncio.run(test())
