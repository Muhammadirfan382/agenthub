"""In-process rate limiting for authentication attempts.

This protects a single worker. It is the right size for the current deployment
(one process) and deliberately not presented as more: a multi-process or
multi-host deployment needs a shared store (Redis), which arrives with the
infrastructure phases.
"""

import time
from collections import defaultdict, deque
from threading import Lock


class SlidingWindowLimiter:
    """Allows `limit` events per key within `window_seconds`."""

    def __init__(self, limit: int, window_seconds: int) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._events: defaultdict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def _prune(self, key: str, now: float) -> deque[float]:
        events = self._events[key]
        cutoff = now - self.window_seconds
        while events and events[0] <= cutoff:
            events.popleft()
        return events

    def check(self, key: str) -> bool:
        """True when the key is still under the limit. Does not record anything."""
        with self._lock:
            return len(self._prune(key, time.monotonic())) < self.limit

    def record(self, key: str) -> None:
        with self._lock:
            now = time.monotonic()
            self._prune(key, now).append(now)

    def reset(self, key: str) -> None:
        """Called after a success, so one good login clears the failure count."""
        with self._lock:
            self._events.pop(key, None)

    def retry_after_seconds(self, key: str) -> int:
        with self._lock:
            events = self._prune(key, time.monotonic())
            if len(events) < self.limit:
                return 0
            return max(1, int(self.window_seconds - (time.monotonic() - events[0])))

    def clear(self) -> None:
        with self._lock:
            self._events.clear()
