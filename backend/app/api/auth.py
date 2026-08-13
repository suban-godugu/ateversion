from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthUser, get_current_user, rate_limit_dependency
from app.core.config import get_settings
from app.core.database import get_db
from app.core.logging import get_logger
from app.core.rate_limit import auth_limiter, client_key
from app.core.rbac import permissions_for
from app.core.security import create_access_token, hash_password, verify_password
from app.models.entities import AuditLog, User
from app.repositories.event_repo import AuditLogRepository
from app.schemas.auth import LoginRequest, TokenResponse, UserOut
from app.services.unit_of_work import transactional_session

router = APIRouter(tags=["auth"])
logger = get_logger("auth")


@router.post("/auth/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    auth_limiter.check(client_key(request, "auth"))
    user = (
        await db.execute(select(User).where(User.username == body.username.strip()))
    ).scalar_one_or_none()
    if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
        logger.warning("login_failed", extra={"user": body.username, "path": "/auth/login"})
        raise HTTPException(status_code=401, detail="Invalid credentials")

    settings = get_settings()
    token = create_access_token(
        subject=user.user_id,
        role=user.role,
        extra={"username": user.username},
    )
    user.last_login_at = datetime.utcnow()
    await AuditLogRepository(db).write(
        actor=user.username,
        action="login",
        entity_type="user",
        entity_id=user.user_id,
        detail="Successful login",
    )
    await db.commit()
    logger.info("login_ok", extra={"user": user.username, "role": user.role})
    return TokenResponse(
        access_token=token,
        role=user.role,  # type: ignore[arg-type]
        username=user.username,
        user_id=user.user_id,
        expires_in_minutes=settings.jwt_expire_minutes,
    )


@router.get("/auth/me", response_model=UserOut)
async def me(user: AuthUser = Depends(get_current_user)) -> UserOut:
    return UserOut(
        user_id=user.user_id,
        username=user.username,
        full_name=user.full_name,
        role=user.role,
        permissions=sorted(p.value for p in permissions_for(user.role)),
    )


async def ensure_seed_users(db: AsyncSession) -> None:
    """Idempotent default users for local/demo hardening."""
    defaults = [
        ("viewer", "viewer123", "VIEWER", "Floor Viewer"),
        ("test_eng", "test123", "TEST_ENGINEER", "Test Engineer"),
        ("process_eng", "process123", "PROCESS_ENGINEER", "Process Engineer"),
        ("ai_eng", "ai123", "AI_ENGINEER", "AI Engineer"),
        ("maint_eng", "maint123", "MAINTENANCE_ENGINEER", "Maintenance Engineer"),
        ("admin", "admin123", "ADMIN", "Administrator"),
    ]
    for username, password, role, full_name in defaults:
        existing = (
            await db.execute(select(User).where(User.username == username))
        ).scalar_one_or_none()
        if existing:
            continue
        db.add(
            User(
                user_id=str(uuid4()),
                username=username,
                full_name=full_name,
                password_hash=hash_password(password),
                role=role,
                is_active=True,
            )
        )
    await db.commit()
