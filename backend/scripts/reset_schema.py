"""Drop and recreate PostgreSQL schema from SQLAlchemy models, then stamp Alembic."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import text

from app.core.database import Base, engine, init_db
from app import models  # noqa: F401


async def main() -> None:
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        await conn.execute(text("GRANT ALL ON SCHEMA public TO CURRENT_USER"))
        await conn.execute(text("GRANT ALL ON SCHEMA public TO public"))
    await init_db()
    print("Schema recreated from SQLAlchemy models.")
    print("Run: alembic stamp head")


if __name__ == "__main__":
    asyncio.run(main())
