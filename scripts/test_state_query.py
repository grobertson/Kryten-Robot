"""Test State Query Endpoint

Quick test script to query the new state endpoint from Kryten-Robot.
Uses the unified command pattern: kryten.robot.command
"""

import asyncio
import json

from nats.aio.client import Client as NATS


async def test_state_query():
    """Test querying state from Kryten-Robot via unified command pattern."""
    nc = NATS()

    try:
        # Connect to NATS
        await nc.connect("nats://localhost:4222")
        print("Connected to NATS")

        # Query the unified command endpoint
        subject = "kryten.robot.command"
        print(f"Querying: {subject}")

        # Send request for all state
        request = {"service": "robot", "command": "state.all"}
        request_bytes = json.dumps(request).encode("utf-8")

        response = await nc.request(subject, request_bytes, timeout=5.0)

        # Parse response
        data = json.loads(response.data.decode("utf-8"))

        print("\n" + "=" * 60)
        print("STATE QUERY RESPONSE")
        print("=" * 60)

        if data.get("success"):
            state = data.get("data", {})
            stats = data.get("stats", {})

            print("\n✅ Success!")
            print(f"\nEmotes: {len(state.get('emotes', []))} loaded")
            print(f"Playlist: {len(state.get('playlist', []))} items")
            print(f"Userlist: {len(state.get('userlist', []))} users")

            # Show stats
            print("\nStateManager Stats:")
            for key, value in stats.items():
                print(f"  {key}: {value}")

            # Show sample data
            if state.get("emotes"):
                print("\nSample emotes (first 5):")
                for emote in state["emotes"][:5]:
                    print(f"  {emote.get('name', 'unknown')}")

            if state.get("playlist"):
                print("\nSample playlist (first 3):")
                for item in state["playlist"][:3]:
                    print(f"  {item.get('title', 'unknown')} [{item.get('type', '?')}]")

            if state.get("userlist"):
                print("\nSample users (first 5):")
                for user in state["userlist"][:5]:
                    print(f"  {user.get('name', 'unknown')} (rank: {user.get('rank', 0)})")

        else:
            print(f"\n❌ Error: {data.get('error', 'Unknown error')}")

        print("\n" + "=" * 60)

    except TimeoutError:
        print("❌ Timeout: No response from state query endpoint")
        print("   Make sure Kryten-Robot is running with StateManager enabled")

    except Exception as e:
        print(f"❌ Error: {e}")

    finally:
        await nc.close()
        print("\nDisconnected from NATS")


if __name__ == "__main__":
    asyncio.run(test_state_query())
