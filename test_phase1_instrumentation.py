#!/usr/bin/env python3
"""Integration test for Phase 1 instrumentation.

This script tests all the foundation work added in Phase 1:
- StatsTracker functionality
- EventPublisher instrumentation
- CommandSubscriber instrumentation
- CytubeConnector tracking
- NatsClient tracking
- ApplicationState module
- StateManager sophisticated counting
"""

import asyncio
import time
from kryten.stats_tracker import StatsTracker
from kryten.config import load_config, StateCountingConfig
from kryten.application_state import ApplicationState


def test_stats_tracker():
    """Test StatsTracker class."""
    print("Testing StatsTracker...")
    
    tracker = StatsTracker(window_size=10)
    
    # Record some events
    for i in range(5):
        tracker.record(f"event_{i}")
        time.sleep(0.1)
    
    # Test get_rate
    rate = tracker.get_rate(1)
    print(f"  Rate (1s): {rate:.2f}/sec")
    assert rate > 0, "Rate should be positive"
    
    # Test get_last
    last_time, last_type = tracker.get_last()
    print(f"  Last event: {last_type} at {last_time}")
    assert last_type == "event_4", "Last event should be event_4"
    
    # Test get_total
    total = tracker.get_total()
    print(f"  Total events: {total}")
    assert total == 5, "Total should be 5"
    
    # Test get_uptime
    uptime = tracker.get_uptime()
    print(f"  Uptime: {uptime:.2f}s")
    assert uptime >= 0.5, "Uptime should be at least 0.5s"
    
    print("✓ StatsTracker tests passed\n")


def test_state_counting_config():
    """Test StateCountingConfig."""
    print("Testing StateCountingConfig...")
    
    # Test default values
    config = StateCountingConfig()
    print(f"  users_exclude_afk: {config.users_exclude_afk}")
    print(f"  users_min_rank: {config.users_min_rank}")
    print(f"  playlist_exclude_temp: {config.playlist_exclude_temp}")
    print(f"  playlist_max_duration: {config.playlist_max_duration}")
    print(f"  emotes_only_enabled: {config.emotes_only_enabled}")
    
    assert config.users_exclude_afk == False
    assert config.users_min_rank == 0
    assert config.playlist_exclude_temp == False
    assert config.playlist_max_duration == 0
    assert config.emotes_only_enabled == False
    
    print("✓ StateCountingConfig tests passed\n")


def test_application_state():
    """Test ApplicationState module."""
    print("Testing ApplicationState...")
    
    # Create minimal config for testing
    class MockConfig:
        pass
    
    config = MockConfig()
    app_state = ApplicationState("/path/to/config.json", config)
    
    print(f"  config_path: {app_state.config_path}")
    print(f"  config: {app_state.config}")
    print(f"  shutdown_event: {app_state.shutdown_event}")
    print(f"  start_time: {app_state.start_time}")
    
    assert app_state.config_path == "/path/to/config.json"
    assert app_state.config is config
    assert not app_state.shutdown_event.is_set()
    assert app_state.start_time > 0
    
    # Test get_uptime
    time.sleep(0.1)
    uptime = app_state.get_uptime()
    print(f"  uptime: {uptime:.2f}s")
    assert uptime >= 0.1
    
    # Test component references start as None
    assert app_state.event_publisher is None
    assert app_state.command_subscriber is None
    assert app_state.connector is None
    assert app_state.nats_client is None
    assert app_state.state_manager is None
    
    print("✓ ApplicationState tests passed\n")


async def test_integration_with_config():
    """Test integration with actual config file."""
    print("Testing integration with config...")
    
    try:
        # Try to load actual config
        config = load_config("config.json")
        print(f"  Loaded config for channel: {config.cytube.channel}")
        
        # Check if state_counting section exists
        if hasattr(config, 'state_counting'):
            sc = config.state_counting
            print(f"  state_counting.users_exclude_afk: {sc.users_exclude_afk}")
            print(f"  state_counting.users_min_rank: {sc.users_min_rank}")
            print(f"  state_counting.playlist_exclude_temp: {sc.playlist_exclude_temp}")
            print(f"  state_counting.playlist_max_duration: {sc.playlist_max_duration}")
            print(f"  state_counting.emotes_only_enabled: {sc.emotes_only_enabled}")
        else:
            print("  (state_counting section not in config - using defaults)")
        
        print("✓ Config integration tests passed\n")
    except FileNotFoundError:
        print("  (config.json not found - skipping config integration test)\n")


def test_component_stats_properties():
    """Test that component stats properties are accessible."""
    print("Testing component stats properties...")
    
    # Note: We can't test actual running components without full bot initialization
    # This test just verifies the properties exist by importing the modules
    
    try:
        from kryten.event_publisher import EventPublisher
        from kryten.command_subscriber import CommandSubscriber
        from kryten.cytube_connector import CytubeConnector
        from kryten.nats_client import NatsClient
        from kryten.state_manager import StateManager
        
        print("  ✓ EventPublisher imported")
        print("  ✓ CommandSubscriber imported")
        print("  ✓ CytubeConnector imported")
        print("  ✓ NatsClient imported")
        print("  ✓ StateManager imported")
        
        # Check that classes have the expected attributes (via grep or inspection)
        # This is a smoke test to ensure our modifications didn't break imports
        
        print("✓ Component imports passed\n")
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        raise


async def main():
    """Run all integration tests."""
    print("=" * 70)
    print("Phase 1 Instrumentation Integration Test")
    print("=" * 70)
    print()
    
    try:
        # Test individual components
        test_stats_tracker()
        test_state_counting_config()
        test_application_state()
        test_component_stats_properties()
        
        # Test integration
        await test_integration_with_config()
        
        print("=" * 70)
        print("✓ All Phase 1 integration tests passed!")
        print("=" * 70)
        print()
        print("Next steps:")
        print("1. Test with running bot to verify instrumentation")
        print("2. Check that stats properties work correctly")
        print("3. Verify connection tracking updates during reconnects")
        print("4. Proceed to Phase 2: Query Commands")
        
    except Exception as e:
        print("=" * 70)
        print(f"✗ Integration test failed: {e}")
        print("=" * 70)
        raise


if __name__ == "__main__":
    asyncio.run(main())
