"""Shmoo ML optimization API — upload, plot, PDF report."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.api.deps import AuthUser, require_permissions
from app.core.rbac import Permission
from app.repositories.event_repo import AuditLogRepository
from app.core.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession

from app.shmoo.service import (
    generate_shmoo_report,
    plot_path_for,
    process_shmoo_upload,
)

router = APIRouter(prefix="/shmoo", tags=["shmoo"])


class ShmooReportRequest(BaseModel):
    session_id: str
    text_mode: str = Field(default="template")


@router.post("/upload")
async def upload_shmoo(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(require_permissions(Permission.WRITE_TELEMETRY)),
) -> dict:
    """
    Upload Shmoo CSV/XLSX → preprocess, train LightGBM/RANSAC, return results + plot URL.
    Requires WRITE_TELEMETRY.
    """
    result = await process_shmoo_upload(file)
    await AuditLogRepository(db).write(
        actor=user.username,
        action="shmoo_upload",
        entity_type="shmoo_session",
        entity_id=result["session_id"],
        detail=f"Shmoo upload {result.get('filename')} · CV={result['results'].get('cv_accuracy')}",
    )
    await db.commit()
    return {"status": "ok", **result}


@router.get("/plot/{session_id}.png")
@router.get("/plot/{session_id}")
async def get_shmoo_plot(session_id: str) -> FileResponse:
    """Serve dark-theme Shmoo plot PNG (UUID session id is the access key)."""
    sid = session_id.removesuffix(".png")
    path = plot_path_for(sid)
    return FileResponse(path, media_type="image/png", filename=f"{sid}_web.png")


@router.post("/report")
async def shmoo_report(
    body: ShmooReportRequest,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(require_permissions(Permission.WRITE_TELEMETRY)),
) -> FileResponse:
    """Generate executive PDF report (template narrative)."""
    report_path = generate_shmoo_report(body.session_id, text_mode=body.text_mode)
    await AuditLogRepository(db).write(
        actor=user.username,
        action="shmoo_report",
        entity_type="shmoo_session",
        entity_id=body.session_id,
        detail="Generated Shmoo PDF report",
    )
    await db.commit()
    die = "D0001"
    try:
        from app.shmoo.service import get_session

        die = str(get_session(body.session_id)["meta"].get("die_id") or "D0001")
    except Exception:
        pass
    return FileResponse(
        report_path,
        media_type="application/pdf",
        filename=f"SHMOO_Analysis_Report_{die}.pdf",
    )
