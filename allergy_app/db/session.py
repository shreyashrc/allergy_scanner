from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from . import tables  # noqa: F401
from allergy_app.core.config import DATABASE_URL
import os


def _ensure_sqlite_parent_dir(db_url: str) -> None:
    if not db_url.startswith("sqlite+aiosqlite:"):
        return
    # sqlite+aiosqlite:////absolute/path.db or sqlite+aiosqlite:///relative.db
    if db_url.startswith("sqlite+aiosqlite:////"):
        path_part = db_url.split("sqlite+aiosqlite:////", 1)[1]
        db_path = "/" + path_part
    else:
        path_part = db_url.split("sqlite+aiosqlite:///", 1)[1]
        if path_part in ("", ":memory:"):
            return
        db_path = os.path.join(os.getcwd(), path_part.lstrip("/"))
    parent = os.path.dirname(db_path) or "."
    try:
        os.makedirs(parent, exist_ok=True)
    except Exception:
        pass


_ensure_sqlite_parent_dir(DATABASE_URL)
engine = create_async_engine(DATABASE_URL, future=True, echo=False)
AsyncSessionMaker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def get_db():
    async with AsyncSessionMaker() as session:
        yield session

