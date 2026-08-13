from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionLocal


@asynccontextmanager
async def transactional_session(
    session: AsyncSession | None = None,
) -> AsyncIterator[AsyncSession]:
    """
    Transactional unit of work.

    If a session is provided (e.g. FastAPI Depends), commit/rollback that session.
    Otherwise open a short-lived session.
    """
    owns = session is None
    db = session or SessionLocal()
    try:
        yield db
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    finally:
        if owns:
            await db.close()
