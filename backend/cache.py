import json
import time
import hashlib
from functools import wraps

try:
    import redis as _redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class NullCache:
    def __init__(self): self._store = {}
    def get(self, key): return self._store.get(key)
    def set(self, key, val, ttl=300): self._store[key] = val
    def delete(self, key): self._store.pop(key, None)
    def flush(self): self._store.clear()


class RedisCache:
    def __init__(self, host='localhost', port=6379, db=0, prefix='baiyun:'):
        self.prefix = prefix
        self.client = _redis.Redis(host=host, port=port, db=db,
                                   decode_responses=True,
                                   socket_connect_timeout=2,
                                   socket_timeout=3)

    def get(self, key):
        val = self.client.get(self.prefix + key)
        return json.loads(val) if val else None

    def set(self, key, val, ttl=300):
        self.client.setex(self.prefix + key, ttl, json.dumps(val, ensure_ascii=False))

    def delete(self, key):
        self.client.delete(self.prefix + key)

    def flush(self):
        for k in self.client.scan_iter(match=self.prefix + '*'):
            self.client.delete(k)


def make_cache(config):
    if not config.CACHE_ENABLED:
        return NullCache()
    if REDIS_AVAILABLE:
        try:
            rc = RedisCache(host=config.REDIS_HOST, port=config.REDIS_PORT,
                            db=config.REDIS_DB, prefix=config.CACHE_PREFIX)
            rc.client.ping()
            return rc
        except Exception:
            pass
    return NullCache()


def cached(cache, ttl=300):
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            key = hashlib.md5(
                (fn.__name__ + ':' + str(args) + ':' + str(sorted(kwargs.items()))).encode()
            ).hexdigest()
            hit = cache.get(key)
            if hit is not None:
                return hit
            result = fn(*args, **kwargs)
            cache.set(key, result, ttl=ttl)
            return result
        return wrapper
    return deco
