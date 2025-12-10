#!/usr/bin/env python3
"""Quick test to verify last_event_time/type are now populated."""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "kryten-py" / "src"))

from kryten import KrytenClient


async def test_last_event():
    config = {
        "nats": {"servers": ["nats://localhost:4222"]},
        "channels": [{"domain": "cytu.be", "channel": "420grindhouse"}]
    }
    
    client = KrytenClient(config)
    await client.connect()
    
    try:
        stats = await client.get_stats()
        events = stats.get("events", {})
        
        print("Events stats:")
        print(f"  Published: {events.get('published', 0)}")
        print(f"  Rate (1m): {events.get('rate_1min', 0):.2f}/sec")
        print(f"  Last event time: {events.get('last_event_time', 'null')}")
        print(f"  Last event type: {events.get('last_event_type', 'null')}")
        
        if events.get('last_event_time') and events.get('last_event_type'):
            print("\n✅ last_event_time and last_event_type are now populated!")
        else:
            print("\n❌ last_event_time and/or last_event_type are still null")
            sys.exit(1)
        
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(test_last_event())
