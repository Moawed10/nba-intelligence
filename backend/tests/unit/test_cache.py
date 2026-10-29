from app.services.cache import Memo, VersionedCache


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_memo_recomputes_after_ttl():
    clock = Clock()
    memo: Memo[int] = Memo(30, clock)
    calls = iter(range(10))
    assert memo.get(lambda: next(calls)) == 0
    clock.now = 29
    assert memo.get(lambda: next(calls)) == 0
    clock.now = 30
    assert memo.get(lambda: next(calls)) == 1
    memo.clear()
    assert memo.get(lambda: next(calls)) == 2


def test_versioned_cache_keys_on_data_version():
    cache = VersionedCache()
    calls = []

    def compute():
        calls.append(1)
        return len(calls)

    assert cache.get_or_set("ns", 60, "k", 1, compute) == 1
    assert cache.get_or_set("ns", 60, "k", 1, compute) == 1
    assert cache.get_or_set("ns", 60, "k", 2, compute) == 2
    assert cache.get_or_set("other", 60, "k", 2, compute) == 3
    cache.clear()
    assert cache.get_or_set("ns", 60, "k", 2, compute) == 4


def test_disabled_cache_always_computes():
    cache = VersionedCache(enabled=False)
    values = iter(range(3))
    assert [cache.get_or_set("ns", 60, "k", 1, lambda: next(values)) for _ in range(2)] == [0, 1]
