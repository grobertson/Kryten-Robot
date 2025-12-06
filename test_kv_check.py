"""Quick test to check if KV stores are populated."""
import asyncio
import json
import sys
sys.path.insert(0, 'd:\\Devel\\kryten-py\\src')

from kryten import KrytenClient
from kryten.config import KrytenConfig, NatsConfig, ChannelConfig


async def check_kv_stores():
    """Check KV store contents for channel."""
    config = KrytenConfig(
        nats=NatsConfig(servers=["nats://localhost:4222"]),
        channels=[ChannelConfig(domain="cytu.be", channel="420grindhouse")]
    )
    client = KrytenClient(config)
    
    try:
        print("Connecting to NATS...")
        await client.connect()
        print("✓ Connected to NATS\n")
        
        # Check what channels exist by listing KV buckets
        print("=" * 60)
        print("Checking KV stores...")
        print("=" * 60)
        
        # Try common channel name
        channel = "420grindhouse"
        bucket_prefix = f"cytube_{channel}"
        
        # Check userlist
        print(f"\n1. Userlist ({bucket_prefix}_userlist):")
        try:
            users = await client.kv_get(f"{bucket_prefix}_userlist", "users", default=None, parse_json=True)
            if users is None:
                print("   ✗ Bucket or key not found")
            elif len(users) == 0:
                print("   ⚠ Empty (no users)")
            else:
                print(f"   ✓ Found {len(users)} users")
                for user in users[:3]:  # Show first 3
                    print(f"      - {user.get('name', 'unknown')} (rank {user.get('rank', '?')})")
                if len(users) > 3:
                    print(f"      ... and {len(users) - 3} more")
        except Exception as e:
            print(f"   ✗ Error: {e}")
        
        # Check emotes
        print(f"\n2. Emotes ({bucket_prefix}_emotes):")
        try:
            emotes = await client.kv_get(f"{bucket_prefix}_emotes", "list", default=None, parse_json=True)
            if emotes is None:
                print("   ✗ Bucket or key not found")
            elif len(emotes) == 0:
                print("   ⚠ Empty (no emotes)")
            else:
                print(f"   ✓ Found {len(emotes)} emotes")
                for emote in emotes[:3]:  # Show first 3
                    print(f"      - {emote.get('name', 'unknown')}")
                if len(emotes) > 3:
                    print(f"      ... and {len(emotes) - 3} more")
        except Exception as e:
            print(f"   ✗ Error: {e}")
        
        # Check playlist
        print(f"\n3. Playlist ({bucket_prefix}_playlist):")
        try:
            playlist = await client.kv_get(f"{bucket_prefix}_playlist", "items", default=None, parse_json=True)
            if playlist is None:
                print("   ✗ Bucket or key not found")
            elif len(playlist) == 0:
                print("   ⚠ Empty (no items)")
            else:
                print(f"   ✓ Found {len(playlist)} items")
                for item in playlist[:3]:  # Show first 3
                    media = item.get('media', {})
                    print(f"      - {media.get('title', 'unknown')} ({media.get('duration', '?')}s)")
                if len(playlist) > 3:
                    print(f"      ... and {len(playlist) - 3} more")
        except Exception as e:
            print(f"   ✗ Error: {e}")
        
        print("\n" + "=" * 60)
        print("KV Store Check Complete")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await client.disconnect()
        print("\nDisconnected from NATS")


if __name__ == "__main__":
    asyncio.run(check_kv_stores())
