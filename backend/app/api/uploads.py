from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthUser, require_permissions
from app.core.database import get_db
from app.core.rbac import Permission
from app.repositories.event_repo import AuditLogRepository
from app.services.upload_service import process_upload

router = APIRouter(tags=["uploads"])


@router.post("/uploads")
async def upload_floor_file(
    file: UploadFile = File(...),
    kind: str | None = Form(default="auto"),
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(require_permissions(Permission.WRITE_TELEMETRY)),
) -> dict:
    """
    Upload wafer image, STDF/STIL, or test log for ingestion.
    Requires WRITE_TELEMETRY (TEST_ENGINEER+ / ADMIN).
    """
    result = await process_upload(db, file=file, kind=kind, actor=user.username)
    await AuditLogRepository(db).write(
        actor=user.username,
        action="upload_file",
        entity_type=str(result.get("kind") or "file"),
        entity_id=str(result.get("filename") or file.filename or "upload"),
        detail=f"Uploaded {result.get('kind')} → wafer {result.get('wafer_id')}",
    )
    await db.commit()
    return {"status": "ok", **result}
