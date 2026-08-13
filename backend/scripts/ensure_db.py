"""Create local role/database when POSTGRES_ADMIN_URL is provided."""

from __future__ import annotations

import asyncio
import os
import sys

import asyncpg


async def main() -> None:
    admin = os.environ.get("POSTGRES_ADMIN_URL")
    if not admin:
        print("Set POSTGRES_ADMIN_URL=postgresql://postgres:PASSWORD@127.0.0.1:5432/postgres")
        sys.exit(1)
    # strip SQLAlchemy driver prefix if present
    admin = admin.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(admin)
    exists = await conn.fetchval("SELECT 1 FROM pg_roles WHERE rolname=$1", "wafer_yield")
    if not exists:
        await conn.execute("CREATE USER wafer_yield WITH PASSWORD 'wafer_yield'")
        print("created role wafer_yield")
    db_exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname=$1", "wafer_yield")
    if not db_exists:
        await conn.execute("CREATE DATABASE wafer_yield OWNER wafer_yield")
        print("created database wafer_yield")
    await conn.close()
    print("ok")


if __name__ == "__main__":
    asyncio.run(main())
