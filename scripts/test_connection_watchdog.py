#!/usr/bin/env python3
"""Test script for connection watchdog functionality.

This script demonstrates the watchdog's ability to detect stale connections
and trigger reconnection logic.
"""

import asyncio
import logging

# Add parent directory to path for imports
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from kryten.connection_watchdog import ConnectionWatchdog  # noqa: E402

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("test_watchdog")


async def test_watchdog_basic():
    """Test basic watchdog functionality."""
    logger.info("=" * 60)
    logger.info("Test 1: Basic watchdog functionality")
    logger.info("=" * 60)

    timeout_triggered = False

    async def on_timeout():
        nonlocal timeout_triggered
        logger.info("Timeout callback triggered!")
        timeout_triggered = True

    # Create watchdog with 5 second timeout
    watchdog = ConnectionWatchdog(timeout=5.0, on_timeout=on_timeout, logger=logger)

    await watchdog.start()
    logger.info(f"Watchdog started: {watchdog.stats}")

    # Pet watchdog twice within timeout
    logger.info("Petting watchdog at t=0")
    watchdog.pet()
    await asyncio.sleep(2)

    logger.info("Petting watchdog at t=2")
    watchdog.pet()
    await asyncio.sleep(2)

    logger.info(f"Status at t=4: {watchdog.stats}")
    assert not timeout_triggered, "Should not have timed out yet"

    # Let it timeout
    logger.info("Waiting for timeout (no more pets)...")
    await asyncio.sleep(6)

    logger.info(f"Status after timeout: {watchdog.stats}")
    assert timeout_triggered, "Should have triggered timeout"
    assert watchdog.stats["timeouts_triggered"] == 1

    await watchdog.stop()
    logger.info("✓ Test 1 passed")


async def test_watchdog_disabled():
    """Test watchdog when disabled."""
    logger.info("")
    logger.info("=" * 60)
    logger.info("Test 2: Disabled watchdog")
    logger.info("=" * 60)

    timeout_triggered = False

    async def on_timeout():
        nonlocal timeout_triggered
        timeout_triggered = True

    # Create disabled watchdog
    watchdog = ConnectionWatchdog(timeout=1.0, on_timeout=on_timeout, logger=logger, enabled=False)

    await watchdog.start()
    logger.info(f"Disabled watchdog started: {watchdog.stats}")

    # Wait past timeout period
    await asyncio.sleep(3)

    logger.info(f"Status after wait: {watchdog.stats}")
    assert not timeout_triggered, "Disabled watchdog should not trigger"

    await watchdog.stop()
    logger.info("✓ Test 2 passed")


async def test_watchdog_continuous_feeding():
    """Test watchdog with continuous feeding."""
    logger.info("")
    logger.info("=" * 60)
    logger.info("Test 3: Continuous feeding")
    logger.info("=" * 60)

    timeout_triggered = False

    async def on_timeout():
        nonlocal timeout_triggered
        timeout_triggered = True

    # Create watchdog with 3 second timeout
    watchdog = ConnectionWatchdog(timeout=3.0, on_timeout=on_timeout, logger=logger)

    await watchdog.start()
    logger.info(f"Watchdog started: {watchdog.stats}")

    # Feed continuously for 10 seconds
    logger.info("Feeding watchdog every second for 10 seconds...")
    for i in range(10):
        watchdog.pet()
        await asyncio.sleep(1)
        if i % 2 == 0:
            logger.info(f"  t={i+1}: {watchdog.time_since_last_event():.2f}s since last event")

    logger.info(f"Final status: {watchdog.stats}")
    assert not timeout_triggered, "Should not timeout with continuous feeding"
    assert watchdog.stats["timeouts_triggered"] == 0

    await watchdog.stop()
    logger.info("✓ Test 3 passed")


async def test_watchdog_recovery():
    """Test watchdog recovery after timeout."""
    logger.info("")
    logger.info("=" * 60)
    logger.info("Test 4: Recovery after timeout")
    logger.info("=" * 60)

    timeout_count = 0

    async def on_timeout():
        nonlocal timeout_count
        timeout_count += 1
        logger.info(f"Timeout #{timeout_count} triggered")

    # Create watchdog with short timeout
    watchdog = ConnectionWatchdog(timeout=2.0, on_timeout=on_timeout, logger=logger)

    await watchdog.start()

    # Let it timeout once
    logger.info("Waiting for first timeout...")
    await asyncio.sleep(3)
    assert timeout_count == 1, "Should have one timeout"

    # Feed it and wait (should not timeout)
    logger.info("Feeding watchdog after timeout...")
    watchdog.pet()
    await asyncio.sleep(1)
    assert timeout_count == 1, "Should still have only one timeout"

    # Let it timeout again
    logger.info("Waiting for second timeout...")
    await asyncio.sleep(3)
    assert timeout_count == 2, "Should have two timeouts"

    logger.info(f"Final status: {watchdog.stats}")
    assert watchdog.stats["timeouts_triggered"] == 2

    await watchdog.stop()
    logger.info("✓ Test 4 passed")


async def main():
    """Run all tests."""
    logger.info("Starting Connection Watchdog Tests")
    logger.info("")

    try:
        await test_watchdog_basic()
        await test_watchdog_disabled()
        await test_watchdog_continuous_feeding()
        await test_watchdog_recovery()

        logger.info("")
        logger.info("=" * 60)
        logger.info("✓ All tests passed!")
        logger.info("=" * 60)

    except AssertionError as e:
        logger.error(f"✗ Test failed: {e}")
        return 1
    except Exception as e:
        logger.error(f"✗ Unexpected error: {e}", exc_info=True)
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
