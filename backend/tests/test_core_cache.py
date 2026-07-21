import pytest
import time
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_nullcache_get_missing():
    from cache import NullCache
    c = NullCache()
    assert c.get("nonexistent") is None


def test_nullcache_set_get():
    from cache import NullCache
    c = NullCache()
    c.set("key1", {"data": 42}, ttl=10)
    assert c.get("key1") == {"data": 42}


def test_nullcache_delete():
    from cache import NullCache
    c = NullCache()
    c.set("k", "v")
    c.delete("k")
    assert c.get("k") is None


def test_nullcache_flush():
    from cache import NullCache
    c = NullCache()
    c.set("a", 1)
    c.set("b", 2)
    c.flush()
    assert c.get("a") is None
    assert c.get("b") is None


def test_cached_decorator():
    from cache import NullCache, cached
    c = NullCache()
    call_count = 0

    @cached(c, ttl=30)
    def calc(x):
        nonlocal call_count
        call_count += 1
        return x * 2

    assert calc(5) == 10
    assert call_count == 1
    assert calc(5) == 10
    assert call_count == 1


def test_cached_different_args():
    from cache import NullCache, cached
    c = NullCache()
    call_count = 0

    @cached(c, ttl=30)
    def calc(x):
        nonlocal call_count
        call_count += 1
        return x * 2

    assert calc(5) == 10
    assert calc(10) == 20
    assert call_count == 2


def test_make_cache_disabled():
    from cache import make_cache, NullCache

    class FakeConfig:
        CACHE_ENABLED = False
    assert isinstance(make_cache(FakeConfig()), NullCache)


def test_make_cache_redis_fallback():
    from cache import make_cache, NullCache

    class FakeConfig:
        CACHE_ENABLED = True
        REDIS_HOST = "255.255.255.255"
        REDIS_PORT = 6379
        REDIS_DB = 0
        CACHE_PREFIX = "test:"
    c = make_cache(FakeConfig())
    assert isinstance(c, NullCache)


def test_cached_mutable_values():
    from cache import NullCache, cached
    c = NullCache()

    @cached(c, ttl=30)
    def get_list():
        return [1, 2, 3]

    first = get_list()
    assert first == [1, 2, 3]
    second = get_list()
    assert second == [1, 2, 3]
    assert first is second


def test_cache_none_value():
    from cache import NullCache
    c = NullCache()
    c.set("none", None)
    assert c.get("none") is None
