from __future__ import annotations

import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///allergen_scanner.db")
ACCESS_TOKEN_EXPIRE_HOURS: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_HOURS", "24"))
ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
OFF_API_BASE: str = os.getenv("OFF_API_BASE", "https://world.openfoodfacts.org/api/v0")
CORS_ALLOW_ORIGINS: str = os.getenv("CORS_ALLOW_ORIGINS", "*")
STALE_DAYS: int = int(os.getenv("STALE_DAYS", "7"))

