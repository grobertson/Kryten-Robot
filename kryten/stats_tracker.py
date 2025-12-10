"""Statistics Tracker - Track rates and statistics over time windows.

This module provides the StatsTracker class for monitoring event rates and
maintaining time-windowed statistics for system management and monitoring.
"""

import time
from collections import deque
from typing import Optional, Tuple


class StatsTracker:
    """Track rates and statistics over time windows.
    
    Maintains a rolling window of events with timestamps and types,
    enabling rate calculation over various time periods and access to
    the most recent event information.
    
    Attributes:
        window_size: Maximum number of events to track (default 300 for 5 min at 1/sec).
        
    Examples:
        >>> tracker = StatsTracker()
        >>> tracker.record("chatMsg")
        >>> tracker.record("userJoin")
        >>> print(f"Rate: {tracker.get_rate(60):.2f}/sec")
        >>> last_time, last_type = tracker.get_last()
    """
    
    def __init__(self, window_size: int = 300):
        """Initialize statistics tracker.
        
        Args:
            window_size: Maximum events to track (default 300 = 5 min at 1/sec).
        """
        self._events: deque[Tuple[float, Optional[str]]] = deque(maxlen=window_size)
        self._start_time = time.time()
    
    def record(self, event_type: Optional[str] = None) -> None:
        """Record an event occurrence.
        
        Args:
            event_type: Optional event type/name for tracking.
            
        Examples:
            >>> tracker.record("chatMsg")
            >>> tracker.record()  # Anonymous event
        """
        self._events.append((time.time(), event_type))
    
    def get_rate(self, window_seconds: int) -> float:
        """Get events per second over specified time window.
        
        Args:
            window_seconds: Time window in seconds to calculate rate over.
            
        Returns:
            Events per second over the window, or 0.0 if window is invalid.
            
        Examples:
            >>> rate_1min = tracker.get_rate(60)
            >>> rate_5min = tracker.get_rate(300)
        """
        if window_seconds <= 0:
            return 0.0
            
        cutoff = time.time() - window_seconds
        count = sum(1 for t, _ in self._events if t > cutoff)
        return count / window_seconds
    
    def get_last(self) -> Tuple[Optional[float], Optional[str]]:
        """Get last event time and type.
        
        Returns:
            Tuple of (timestamp, event_type) for most recent event,
            or (None, None) if no events recorded.
            
        Examples:
            >>> timestamp, event_type = tracker.get_last()
            >>> if timestamp:
            ...     print(f"Last: {event_type} at {timestamp}")
        """
        if self._events:
            return self._events[-1]
        return (None, None)
    
    def get_total(self) -> int:
        """Get total events recorded (within window).
        
        Returns:
            Number of events currently in the tracking window.
            
        Examples:
            >>> total = tracker.get_total()
            >>> print(f"Tracked events: {total}")
        """
        return len(self._events)
    
    def get_uptime(self) -> float:
        """Get tracker uptime in seconds.
        
        Returns:
            Seconds since tracker was created.
            
        Examples:
            >>> uptime = tracker.get_uptime()
            >>> print(f"Uptime: {uptime / 3600:.1f} hours")
        """
        return time.time() - self._start_time
