from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.logging import get_logger
from app.core.rate_limit import api_limiter, client_key
from app.core.rbac import Permission, Role, has_permission
from app.core.security import decode_access_token
from app.models.entities import User

logger = get_logger("auth")
bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class AuthUser:
    user_id: str
    username: str
    role: Role
    full_name: str = ""

    def can(self, permission: Permission) -> bool:
        return has_permission(self.role, permission)


async def rate_limit_dependency(request: Request) -> None:
    api_limiter.check(client_key(request, "api"))


async def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> AuthUser:
    settings = get_settings()
    if settings.auth_disabled:
        return AuthUser(user_id="dev", username="dev", role=Role.ADMIN, full_name="Dev Breakglass")

    token = None
    if creds and creds.scheme.lower() == "bearer":
        token = creds.credentials
    if not token:
        # Also accept Authorization already parsed, or query for WS upgrade helpers
        auth = request.headers.get("authorization") or ""
        if auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1].strip()

    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    try:
        payload = decode_access_token(token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    user = await db.get(User, payload["sub"])
    if user is None or not user.is_active:
        # Allow token-only identity if user row missing (rotated DB) — still enforce role claim
        try:
            role = Role(payload["role"])
        except ValueError as exc:
            raise HTTPException(status_code=401, detail="Invalid role") from exc
        return AuthUser(user_id=str(payload["sub"]), username=str(payload.get("username", payload["sub"])), role=role)

    try:
        role = Role(user.role)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="Invalid user role") from exc

    return AuthUser(
        user_id=user.user_id,
        username=user.username,
        role=role,
        full_name=user.full_name,
    )


def require_permissions(*permissions: Permission):
    async def _dep(user: AuthUser = Depends(get_current_user)) -> AuthUser:
        missing = [p.value for p in permissions if not user.can(p)]
        if missing:
            logger.warning(
                "authorization_denied",
                extra={"user": user.username, "role": user.role.value, "extra": {"missing": missing}},
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing permissions: {', '.join(missing)}",
            )
        return user

    return _dep


def require_roles(*roles: Role):
    async def _dep(user: AuthUser = Depends(get_current_user)) -> AuthUser:
        if user.role not in roles and user.role != Role.ADMIN:
            raise HTTPException(status_code=403, detail="Insufficient role")
        return user

    return _dep
