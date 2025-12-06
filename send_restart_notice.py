"""Send Groupwide Restart Notice

Simple script to send a restart notice to all Kryten services.
"""

import asyncio
import json
import sys
from datetime import datetime
from nats.aio.client import Client as NATS


async def send_restart_notice(reason: str, delay: int = 5):
    """Send groupwide restart notice."""
    nc = NATS()
    
    try:
        await nc.connect("nats://localhost:4222")
        print(f"✅ Connected to NATS")
        
        subject = "kryten.lifecycle.group.restart"
        payload = {
            "initiator": "admin",
            "reason": reason,
            "delay_seconds": delay,
            "timestamp": datetime.now().isoformat()
        }
        
        data_bytes = json.dumps(payload).encode('utf-8')
        await nc.publish(subject, data_bytes)
        
        print(f"\n🔄 Sent groupwide restart notice:")
        print(f"   Reason: {reason}")
        print(f"   Delay: {delay} seconds")
        print(f"   Subject: {subject}")
        print(f"\nAll Kryten services will restart in {delay} seconds.\n")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    
    finally:
        await nc.close()
    
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python send_restart_notice.py <reason> [delay_seconds]")
        print("Example: python send_restart_notice.py 'Configuration update' 10")
        sys.exit(1)
    
    reason = sys.argv[1]
    delay = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    
    exit_code = asyncio.run(send_restart_notice(reason, delay))
    sys.exit(exit_code)
