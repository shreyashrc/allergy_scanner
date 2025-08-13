from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional, Callable

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from allergy_app.core.config import OFF_API_BASE
from allergy_app.db.tables import ApiCache


def sqlite_cache(ttl_seconds: int, key_builder: Callable[..., str]):
    def decorator(func):
        async def wrapper(*args, **kwargs):
            db: Optional[AsyncSession] = kwargs.get("db")
            if db is None:
                return await func(*args, **kwargs)
            key = key_builder(*args, **kwargs)
            now = datetime.now(timezone.utc)
            entry = await db.scalar(select(ApiCache).where(ApiCache.key == key))
            if entry and (now - entry.fetched_at) <= timedelta(seconds=ttl_seconds):
                try:
                    return json.loads(entry.data)
                except Exception:
                    pass
            data = await func(*args, **kwargs)
            if entry:
                entry.data = json.dumps(data)
                entry.fetched_at = now
            else:
                db.add(ApiCache(key=key, data=json.dumps(data), fetched_at=now))
            await db.flush()
            return data
        return wrapper
    return decorator


@sqlite_cache(ttl_seconds=7 * 24 * 3600, key_builder=lambda barcode, **kwargs: f"OFF:product:{barcode}")
async def fetch_product(barcode: str, *, db: AsyncSession) -> Dict[str, Any]:
    url = f"{OFF_API_BASE.rstrip('/')}/product/{barcode}.json"
    timeout = httpx.Timeout(10.0, connect=5.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url)
        return resp.json()
    except Exception as e:
        print(f"Error fetching product {barcode}: {e}")
        return {"status": 0, "error": str(e)}

