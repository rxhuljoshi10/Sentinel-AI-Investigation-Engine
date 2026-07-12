import json
import hashlib
from backend.core.config import settings
import redis.asyncio as redis

_redis_client = None

async def get_redis():
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True
        )
    return _redis_client

def make_cache_key(prefix: str, content: str) -> str:
    """
    Creates a deterministic cache key from content.
    Same log = same key = cache hit.
    """
    content_hash = hashlib.md5(content.encode()).hexdigest()
    return f"sentinel:{prefix}:{content_hash}"

async def get_cached(key: str) -> dict | None:
    try:
        r = await get_redis()
        cached = await r.get(key)
        if cached:
            await r.incr("sentinel:stats:hits")
            # If the cached value is already a dict, return it. Otherwise parse it if it's a string.
            if isinstance(cached, str):
                try:
                    return json.loads(cached)
                except json.JSONDecodeError:
                    return cached
            return cached
        await r.incr("sentinel:stats:misses")
        return None
    except Exception:
        return None

async def set_cached(key: str, value: any, ttl: int = 3600) -> None:
    try:
        r = await get_redis()
        await r.setex(key, ttl, json.dumps(value))
    except Exception:
        pass  # Cache failures should never break the application

async def get_cache_stats() -> dict:
    try:
        r = await get_redis()
        hits = await r.get("sentinel:stats:hits")
        misses = await r.get("sentinel:stats:misses")
        return {
            "hits": int(hits) if hits else 0,
            "misses": int(misses) if misses else 0
        }
    except Exception:
        return {"hits": 0, "misses": 0}