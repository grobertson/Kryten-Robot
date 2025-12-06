"""Test Lifecycle Events

Monitor lifecycle events from all Kryten services and test groupwide restart.
"""

import asyncio
import json
from datetime import datetime
from nats.aio.client import Client as NATS


class LifecycleMonitor:
    """Monitor lifecycle events from Kryten services."""
    
    def __init__(self):
        self.nc = None
        self.subscriptions = []
    
    async def start(self):
        """Connect and subscribe to lifecycle events."""
        self.nc = NATS()
        await self.nc.connect("nats://localhost:4222")
        print("✅ Connected to NATS\n")
        
        # Subscribe to all lifecycle events
        subjects = [
            "kryten.lifecycle.*.startup",
            "kryten.lifecycle.*.shutdown",
            "kryten.lifecycle.*.connected",
            "kryten.lifecycle.*.disconnected",
            "kryten.lifecycle.group.restart"
        ]
        
        for subject in subjects:
            sub = await self.nc.subscribe(subject, cb=self.handle_event)
            self.subscriptions.append(sub)
            print(f"📡 Subscribed to: {subject}")
        
        print("\n" + "=" * 60)
        print("LIFECYCLE EVENT MONITOR")
        print("=" * 60)
        print("Listening for events from all Kryten services...\n")
    
    async def handle_event(self, msg):
        """Handle incoming lifecycle event."""
        try:
            subject = msg.subject
            data = json.loads(msg.data.decode('utf-8'))
            
            # Extract event type from subject
            parts = subject.split('.')
            service = parts[2] if len(parts) > 2 else "unknown"
            event_type = parts[3] if len(parts) > 3 else "unknown"
            
            # Format timestamp
            timestamp = data.get('timestamp', datetime.now().isoformat())
            ts = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            time_str = ts.strftime("%H:%M:%S")
            
            # Build event message
            if event_type == "startup":
                icon = "🚀"
                msg = f"Service started"
                if 'version' in data:
                    msg += f" (v{data['version']})"
                if 'domain' in data and 'channel' in data:
                    msg += f" - {data['domain']}/{data['channel']}"
            
            elif event_type == "shutdown":
                icon = "🛑"
                reason = data.get('reason', 'Unknown')
                msg = f"Service shutdown: {reason}"
                if 'uptime_seconds' in data:
                    uptime = int(data['uptime_seconds'])
                    msg += f" (uptime: {uptime}s)"
            
            elif event_type == "connected":
                icon = "🔗"
                target = data.get('target', 'Unknown')
                msg = f"Connected to {target}"
                if 'servers' in data:
                    msg += f" ({data['servers']})"
                elif 'domain' in data:
                    msg += f" ({data['domain']}/{data.get('channel', '')})"
            
            elif event_type == "disconnected":
                icon = "⚠️"
                target = data.get('target', 'Unknown')
                reason = data.get('reason', 'Unknown')
                msg = f"Disconnected from {target}: {reason}"
            
            elif event_type == "restart":
                icon = "🔄"
                service = data.get('initiator', 'unknown')
                reason = data.get('reason', 'No reason')
                delay = data.get('delay_seconds', 0)
                msg = f"GROUP RESTART requested: {reason} (delay: {delay}s)"
            
            else:
                icon = "📋"
                msg = f"Event: {event_type}"
            
            # Print formatted event
            hostname = data.get('hostname', 'unknown')
            print(f"{icon} [{time_str}] {service}@{hostname}: {msg}")
        
        except Exception as e:
            print(f"❌ Error handling event: {e}")
    
    async def send_restart_notice(self, reason: str = "Manual test", delay: int = 5):
        """Send groupwide restart notice."""
        subject = "kryten.lifecycle.group.restart"
        payload = {
            "initiator": "test-script",
            "reason": reason,
            "delay_seconds": delay,
            "timestamp": datetime.now().isoformat()
        }
        
        data_bytes = json.dumps(payload).encode('utf-8')
        await self.nc.publish(subject, data_bytes)
        print(f"\n🔄 Sent groupwide restart notice: {reason} (delay: {delay}s)\n")
    
    async def stop(self):
        """Disconnect from NATS."""
        for sub in self.subscriptions:
            await sub.unsubscribe()
        await self.nc.close()
        print("\n✅ Disconnected from NATS")


async def interactive_menu(monitor: LifecycleMonitor):
    """Interactive menu for testing."""
    print("\n" + "=" * 60)
    print("INTERACTIVE MENU")
    print("=" * 60)
    print("Commands:")
    print("  r <reason> - Send restart notice with reason")
    print("  q          - Quit monitor")
    print("=" * 60)
    print()


async def main():
    """Main test function."""
    monitor = LifecycleMonitor()
    
    try:
        await monitor.start()
        
        # Run menu in background
        await interactive_menu(monitor)
        
        # Keep monitoring until interrupted
        while True:
            try:
                # Simple command input (non-blocking would be better but this works)
                print("Enter command (r <reason> | q): ", end='', flush=True)
                await asyncio.sleep(0.1)  # Small delay to not block event handling
                
                # Just keep monitoring
                await asyncio.sleep(1)
            
            except KeyboardInterrupt:
                break
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    
    finally:
        await monitor.stop()


if __name__ == "__main__":
    print("""
╔════════════════════════════════════════════════════════════╗
║         KRYTEN LIFECYCLE EVENT MONITOR                     ║
╚════════════════════════════════════════════════════════════╝

This script monitors lifecycle events from all Kryten services:
  - Service startup/shutdown
  - Connection/disconnection events
  - Groupwide restart notices

To send a restart notice, use another terminal:
  nats pub kryten.lifecycle.group.restart '{"initiator":"test","reason":"Testing","delay_seconds":5}'

Press Ctrl+C to exit
""")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n✅ Monitor stopped")
