"""Pembatas percobaan gagal (di memori; cukup untuk satu proses server)."""
import threading
import time


class FailLimiter:
    def __init__(self, max_fail: int = 5, window_seconds: int = 900):
        self.max_fail = max_fail
        self.window = window_seconds
        self._hits: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> list[float]:
        recent = [t for t in self._hits.get(key, []) if now - t < self.window]
        if recent:
            self._hits[key] = recent
        else:
            self._hits.pop(key, None)
        return recent

    def blocked_for(self, key: str) -> int:
        """Sisa detik pemblokiran (0 = boleh mencoba)."""
        now = time.monotonic()
        with self._lock:
            recent = self._prune(key, now)
            if len(recent) < self.max_fail:
                return 0
            return max(1, int(self.window - (now - recent[0])))

    def fail(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            self._prune(key, now)
            self._hits.setdefault(key, []).append(now)

    def reset(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = FailLimiter()
