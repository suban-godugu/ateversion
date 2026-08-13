"""File upload ingestion: wafer images, STDF/STIL, and test logs."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion.wafer_image_ingest import image_to_die_bins
from app.models.entities import DashboardState, Wafer
from app.schemas.events import EventType, TelemetryEvent
from app.services.telemetry_service import ingest_events

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff"}
STIL_EXTS = {".stil", ".stilt"}
STDF_EXTS = {".stdf", ".std", ".atr"}
LOG_EXTS = {".log", ".txt", ".csv"}

BIN_TO_EVENT = {
    "pass": EventType.die_pass,
    "fail": EventType.die_fail,
    "retest": EventType.die_retest,
    "reclass": EventType.die_reclassified,
}


def classify_upload(filename: str, declared_kind: str | None) -> str:
    kind = (declared_kind or "auto").strip().lower()
    ext = Path(filename).suffix.lower()
    if kind in {"wafer_image", "image", "wafer"}:
        return "wafer_image"
    if kind in {"stil", "stdf", "test_pattern"}:
        return "stil" if kind == "stil" or ext in STIL_EXTS else "stdf"
    if kind in {"log", "test_log"}:
        return "log"
    if ext in IMAGE_EXTS:
        return "wafer_image"
    if ext in STIL_EXTS:
        return "stil"
    if ext in STDF_EXTS:
        return "stdf"
    if ext in LOG_EXTS:
        return "log"
    raise HTTPException(
        status_code=422,
        detail="Unsupported file type. Upload wafer image, STDF/STIL, or log file.",
    )


async def _active_context(db: AsyncSession) -> tuple[str, str, str, str]:
    state = await db.get(DashboardState, 1)
    wafer_id = state.active_wafer_id if state else None
    lot_id = "24601-07"
    tester_id = "ATE-04"
    site_id = "1"
    if wafer_id:
        wafer = await db.get(Wafer, wafer_id)
        if wafer:
            lot_id = wafer.lot_id or lot_id
            tester_id = wafer.tester_id or tester_id
            site_id = wafer.site_id or site_id
            return wafer_id, lot_id, tester_id, site_id
    # Fallback to newest wafer
    wafer = (
        await db.execute(select(Wafer).order_by(Wafer.updated_at.desc()).limit(1))
    ).scalar_one_or_none()
    if wafer:
        return wafer.wafer_id, wafer.lot_id, wafer.tester_id or tester_id, wafer.site_id or site_id
    raise HTTPException(status_code=400, detail="No active wafer available for upload ingest")


async def _next_seq(db: AsyncSession) -> int:
    from app.models.entities import TelemetryEventRow

    last = (
        await db.execute(
            select(TelemetryEventRow.sequence_number).order_by(TelemetryEventRow.sequence_number.desc()).limit(1)
        )
    ).scalar_one_or_none()
    return int(last or 1_000_000) + 1


async def ingest_wafer_image(
    db: AsyncSession,
    *,
    file: UploadFile,
    actor: str,
) -> dict:
    suffix = Path(file.filename or "wafer.png").suffix.lower() or ".png"
    if suffix not in IMAGE_EXTS:
        raise HTTPException(status_code=422, detail="Wafer image must be png/jpg/bmp/webp")

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=422, detail="Empty file")
    if len(raw) > 12 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image too large (max 12MB)")

    with NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(raw)
        tmp_path = Path(tmp.name)

    try:
        dies = image_to_die_bins(tmp_path)
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass

    if not dies:
        raise HTTPException(status_code=422, detail="Could not extract dies from wafer image")

    wafer_id, lot_id, tester_id, site_id = await _active_context(db)
    seq = await _next_seq(db)
    now = datetime.utcnow()
    events: list[TelemetryEvent] = [
        TelemetryEvent(
            event_id=str(uuid4()),
            event_type=EventType.wafer_started,
            timestamp=now,
            source="ingestion",
            tester_id=tester_id,
            site_id=site_id,
            lot_id=lot_id,
            wafer_id=wafer_id,
            sequence_number=seq,
            payload={
                "total_dies": len(dies),
                "caption": f"Live wafer map · Lot {lot_id}",
                "source_image": file.filename,
                "uploaded_by": actor,
            },
        )
    ]
    seq += 1
    for die in dies:
        b = die["bin"]
        events.append(
            TelemetryEvent(
                event_id=str(uuid4()),
                event_type=BIN_TO_EVENT[b],
                timestamp=now,
                source="ingestion",
                tester_id=tester_id,
                site_id=site_id,
                lot_id=lot_id,
                wafer_id=wafer_id,
                die_id=die["die_id"],
                sequence_number=seq,
                payload={
                    "x": die["x"],
                    "y": die["y"],
                    "bin": b,
                    "fail_code": {"fail": "BIN_FAIL", "retest": "MARGINAL", "reclass": "FF_OVERTURN"}.get(b),
                    "confidence": {"pass": 0.97, "reclass": 0.91, "retest": 0.72, "fail": 0.88}.get(b, 0.5),
                    "uploaded_by": actor,
                },
            )
        )
        seq += 1

    pass_c = sum(1 for d in dies if d["bin"] == "pass")
    reclass_c = sum(1 for d in dies if d["bin"] == "reclass")
    fail_c = sum(1 for d in dies if d["bin"] == "fail")
    retest_c = sum(1 for d in dies if d["bin"] == "retest")
    tested = len(dies)
    yield_pct = round(((pass_c + reclass_c) / tested) * 100, 1) if tested else 0.0
    events.append(
        TelemetryEvent(
            event_id=str(uuid4()),
            event_type=EventType.yield_updated,
            timestamp=now,
            source="ingestion",
            tester_id=tester_id,
            site_id=site_id,
            lot_id=lot_id,
            wafer_id=wafer_id,
            sequence_number=seq,
            payload={
                "yield_pct": yield_pct,
                "pass": pass_c,
                "fail": fail_c,
                "retest": retest_c,
                "reclass": reclass_c,
                "total": tested,
                "uploaded_by": actor,
            },
        )
    )

    # Publish summary events; skip WS storm for die chunks
    await ingest_events(db, events[:1], publish=True, materialize_floor_log=True)
    for i in range(1, len(events) - 1, 200):
        await ingest_events(db, events[i : i + 200], publish=False, materialize_floor_log=False)
    await ingest_events(db, events[-1:], publish=True, materialize_floor_log=True)

    return {
        "kind": "wafer_image",
        "filename": file.filename,
        "wafer_id": wafer_id,
        "dies": tested,
        "yield_pct": yield_pct,
        "bins": {"pass": pass_c, "fail": fail_c, "retest": retest_c, "reclass": reclass_c},
    }


_LINE_RE = re.compile(
    r"(?P<sev>PASS|FAIL|WARN|ERROR|INFO|CRITICAL)?[:\s-]*(?P<body>.+)",
    re.IGNORECASE,
)


async def ingest_text_artifact(
    db: AsyncSession,
    *,
    file: UploadFile,
    kind: str,
    actor: str,
) -> dict:
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=422, detail="Empty file")
    if len(raw) > 8 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large (max 8MB)")

    try:
        text = raw.decode("utf-8", errors="replace")
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Unable to decode file as text") from exc

    wafer_id, lot_id, tester_id, site_id = await _active_context(db)
    seq = await _next_seq(db)
    now = datetime.utcnow()
    source = "stdf" if kind in {"stdf", "stil"} else "test_log"
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    # Cap event fan-out
    sample = lines[:80]
    events: list[TelemetryEvent] = [
        TelemetryEvent(
            event_id=str(uuid4()),
            event_type=EventType.engineering_hold
            if kind == "stil"
            else EventType.tester_status_changed,
            timestamp=now,
            source=source,
            tester_id=tester_id,
            site_id=site_id,
            lot_id=lot_id,
            wafer_id=wafer_id,
            sequence_number=seq,
            payload={
                "upload_kind": kind,
                "filename": file.filename,
                "uploaded_by": actor,
                "line_count": len(lines),
                "preview": sample[:5],
                "message": f"Uploaded {kind.upper()} file {file.filename} ({len(lines)} lines)",
            },
        )
    ]
    seq += 1

    for ln in sample:
        m = _LINE_RE.match(ln)
        body = (m.group("body") if m else ln)[:240]
        sev = (m.group("sev") if m and m.group("sev") else "INFO").upper()
        et = EventType.escape_risk_detected if sev in {"FAIL", "ERROR", "CRITICAL"} else EventType.wafer_progress
        events.append(
            TelemetryEvent(
                event_id=str(uuid4()),
                event_type=et,
                timestamp=now,
                source=source,
                tester_id=tester_id,
                site_id=site_id,
                lot_id=lot_id,
                wafer_id=wafer_id,
                sequence_number=seq,
                payload={
                    "upload_kind": kind,
                    "filename": file.filename,
                    "severity": sev,
                    "message": body,
                    "uploaded_by": actor,
                },
            )
        )
        seq += 1

    accepted = await ingest_events(db, events, publish=True, materialize_floor_log=True)
    return {
        "kind": kind,
        "filename": file.filename,
        "wafer_id": wafer_id,
        "lines": len(lines),
        "events_accepted": len(accepted),
    }


async def process_upload(
    db: AsyncSession,
    *,
    file: UploadFile,
    kind: str | None,
    actor: str,
) -> dict:
    resolved = classify_upload(file.filename or "upload.bin", kind)
    if resolved == "wafer_image":
        return await ingest_wafer_image(db, file=file, actor=actor)
    return await ingest_text_artifact(db, file=file, kind=resolved, actor=actor)
