#!/usr/bin/env python3
"""Quick inline test for system query commands."""

import asyncio
import json

async def test():
    try:
        from nats.aio.client import Client as NATS
    except ImportError:
        print("❌ nats-py not installed. Install with: pip install nats-py")
        return
    
    nc = NATS()
    
    try:
        await nc.connect("nats://localhost:4222")
        print("✓ Connected to NATS\n")
    except Exception as e:
        print(f"❌ Failed to connect to NATS: {e}")
        return
    
    # Test system.ping
    print("Testing system.ping...")
    request = {"service": "robot", "command": "system.ping"}
    try:
        response = await nc.request("kryten.robot.command", json.dumps(request).encode(), timeout=5.0)
        data = json.loads(response.data.decode())
        if data.get("success"):
            print(f"✅ system.ping: {data['data']}\n")
        else:
            print(f"❌ system.ping failed: {data.get('error')}\n")
    except asyncio.TimeoutError:
        print("❌ system.ping: Timeout\n")
    except Exception as e:
        print(f"❌ system.ping: {e}\n")
    
    # Test system.config
    print("Testing system.config...")
    request = {"service": "robot", "command": "system.config"}
    try:
        response = await nc.request("kryten.robot.command", json.dumps(request).encode(), timeout=5.0)
        data = json.loads(response.data.decode())
        if data.get("success"):
            config = data['data']
            print(f"✅ system.config:")
            print(f"   Channel: {config['cytube']['channel']}")
            print(f"   Password: {config['cytube']['password']}")
            print(f"   Log level: {config['log_level']}\n")
        else:
            print(f"❌ system.config failed: {data.get('error')}\n")
    except asyncio.TimeoutError:
        print("❌ system.config: Timeout\n")
    except Exception as e:
        print(f"❌ system.config: {e}\n")
    
    # Test system.stats
    print("Testing system.stats...")
    request = {"service": "robot", "command": "system.stats"}
    try:
        response = await nc.request("kryten.robot.command", json.dumps(request).encode(), timeout=5.0)
        data = json.loads(response.data.decode())
        if data.get("success"):
            stats = data['data']
            print(f"✅ system.stats:")
            print(f"   Uptime: {stats.get('uptime_seconds', 0):.1f}s")
            print(f"   Events published: {stats['events'].get('published', 0)}")
            print(f"   CyTube connected: {stats['connections']['cytube'].get('connected')}")
            print(f"   NATS connected: {stats['connections']['nats'].get('connected')}")
            print(f"   Memory RSS: {stats['memory'].get('rss_mb', 0):.1f} MB\n")
        else:
            print(f"❌ system.stats failed: {data.get('error')}\n")
    except asyncio.TimeoutError:
        print("❌ system.stats: Timeout\n")
    except Exception as e:
        print(f"❌ system.stats: {e}\n")
    
    await nc.close()
    print("All tests complete!")

if __name__ == "__main__":
    asyncio.run(test())
