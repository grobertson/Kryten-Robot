#!/usr/bin/env python3
"""Quick test for system.shutdown with short delay."""

import asyncio
import json


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

    # Test system.shutdown with 5 second delay
    print("Testing system.shutdown with 5 second delay...")
    request = {
        "service": "robot",
        "command": "system.shutdown",
        "delay_seconds": 5,
        "reason": "Quick integration test",
    }

    try:
        response = await nc.request(
            "kryten.robot.command", json.dumps(request).encode(), timeout=5.0
        )
        data = json.loads(response.data.decode())

        if data.get("success"):
            result = data["data"]
            print("✅ system.shutdown accepted:")
            print(f"   Message: {result['message']}")
            print(f"   Delay: {result['delay_seconds']}s")
            print(f"   Shutdown time: {result['shutdown_time']}")
            print(f"   Reason: {result['reason']}")
            print("\n⚠️  Kryten-Robot will shut down in 5 seconds!")
        else:
            print(f"❌ system.shutdown failed: {data.get('error')}")

    except TimeoutError:
        print("❌ Timeout waiting for response")
    except Exception as e:
        print(f"❌ Error: {e}")

    await nc.close()


if __name__ == "__main__":
    asyncio.run(test())
