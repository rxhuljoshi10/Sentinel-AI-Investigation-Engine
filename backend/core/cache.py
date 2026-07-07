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
            return json.loads(cached)
        return None
    except Exception:
        return None

async def set_cached(key: str, value: dict, ttl: int = 3600) -> None:
    try:
        r = await get_redis()
        await r.setex(key, ttl, json.dumps(value))
    except Exception:
        pass  # Cache failures should never break the application