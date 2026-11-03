import math
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

MAX_TRACKED_CLIENTS = 10_000


@dataclass
class _Bucket:
    tokens: float
    updated: float


class TokenBuckets:
    def __init__(
        self, per_minute: int, burst: int, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self.rate = per_minute / 60.0
        self.burst = float(burst)
        self.clock = clock
        self.buckets: dict[str, _Bucket] = {}
        self.lock = threading.Lock()

    def _forget_refilled(self, now: float) -> None:
        for key, bucket in list(self.buckets.items()):
            if bucket.tokens + (now - bucket.updated) * self.rate >= self.burst:
                del self.buckets[key]

    def take(self, key: str) -> int | None:
        now = self.clock()
        with self.lock:
            if len(self.buckets) >= MAX_TRACKED_CLIENTS:
                self._forget_refilled(now)
            bucket = self.buckets.get(key) or _Bucket(self.burst, now)
            bucket.tokens = min(self.burst, bucket.tokens + (now - bucket.updated) * self.rate)
            bucket.updated = now
            self.buckets[key] = bucket
            if bucket.tokens >= 1.0:
                bucket.tokens -= 1.0
                return None
            return max(1, math.ceil((1.0 - bucket.tokens) / self.rate))


class PredictionLimiter:
    def __init__(
        self,
        per_client_minute: int,
        burst: int,
        global_minute: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.clients = TokenBuckets(per_client_minute, burst, clock)
        self.everyone = TokenBuckets(global_minute, global_minute, clock)

    def retry_after(self, client: str) -> int | None:
        return self.clients.take(client) or self.everyone.take("all")


def client_address(peer: str | None, forwarded_for: str | None, trusted: set[str]) -> str:
    address = peer or "unknown"
    if address not in trusted or not forwarded_for:
        return address
    for hop in reversed([h.strip() for h in forwarded_for.split(",") if h.strip()]):
        if hop not in trusted:
            return hop
    return address
