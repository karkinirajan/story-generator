import threading
import time
from collections import deque


class RateLimiter:
    """At most ``limit`` calls per ``window`` seconds for each key (a client address). It lives in one
    process's memory, so with several workers each has its own count; a limit at the proxy is stronger."""

    def __init__(self, limit: int, window: float = 60.0, clock=time.monotonic):
        self.limit, self.window, self.clock = limit, window, clock
        self._hits: dict[str, deque] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> float:
        """0 when allowed (and counted); otherwise the seconds to wait."""
        if self.limit <= 0:
            return 0.0
        now = self.clock()
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and now - hits[0] >= self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                return self.window - (now - hits[0])
            hits.append(now)
            if len(self._hits) > 10_000:  # forget keys that have gone quiet
                self._hits = {
                    k: v for k, v in self._hits.items() if v and now - v[-1] < self.window
                }
            return 0.0
