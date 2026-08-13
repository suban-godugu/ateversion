"""Shmoo upload → preprocess → train → plot → report (ported from shmoo_vl)."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from fastapi import HTTPException, UploadFile

from app.shmoo.data.preprocessor import ShmooPreprocessor
from app.shmoo.ml.model import ShmooModel, ShmooResults
from app.shmoo.report.generator import ReportGenerator
from app.shmoo.report.plot_builder import build_shmoo_plot
from app.shmoo.text.template_engine import TemplateEngine

BASE_DIR = Path(__file__).resolve().parents[2] / "data" / "shmoo"
UPLOAD_DIR = BASE_DIR / "uploads"
REPORT_DIR = BASE_DIR / "reports"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)

SHMOO_EXTS = {".csv", ".xlsx", ".xls"}

# In-memory session store (same pattern as Flask shmoo_vl)
_sessions: dict[str, dict[str, Any]] = {}


def serialize_results(results: ShmooResults) -> dict[str, Any]:
    return {
        "accuracy": round(results.accuracy, 4),
        "cv_accuracy": round(results.cv_accuracy, 4),
        "cv_std": round(results.cv_std, 4),
        "boundary_slope": round(results.boundary_slope, 4),
        "boundary_intercept": round(results.boundary_intercept, 4),
        "boundary_r2": round(results.boundary_r2, 4),
        "recommended_vdd": round(results.recommended_vdd, 3),
        "recommended_freq": round(results.recommended_freq, 3),
        "voltage_margin_v": round(results.voltage_margin_v, 3),
        "freq_margin_ghz": round(results.freq_margin_ghz, 3),
        "n_pass": results.n_pass,
        "n_fail": results.n_fail,
        "failure_code_dist": results.failure_code_dist,
        "critical_fault_patterns": getattr(
            results, "critical_fault_patterns", results.timing_fail_patterns
        ),
        "timing_fail_patterns": results.timing_fail_patterns,
        "yield_by_vdd": {str(k): v for k, v in results.yield_by_vdd.items()},
        "fmax_by_vdd": {str(k): v for k, v in results.fmax_by_vdd.items()},
    }


def get_session(session_id: str) -> dict[str, Any]:
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Shmoo session not found")
    return session


async def process_shmoo_upload(file: UploadFile) -> dict[str, Any]:
    filename = file.filename or "shmoo.csv"
    ext = Path(filename).suffix.lower()
    if ext not in SHMOO_EXTS:
        raise HTTPException(
            status_code=422,
            detail="Unsupported Shmoo file. Upload CSV or Excel (.csv, .xlsx).",
        )

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=422, detail="Empty file")

    session_id = str(uuid.uuid4())
    save_path = UPLOAD_DIR / f"{session_id}{ext}"
    save_path.write_bytes(raw)

    try:
        preprocessor = ShmooPreprocessor()
        meta = preprocessor.load(str(save_path))
        df = preprocessor.process()

        model = ShmooModel()
        results = model.train_and_evaluate(df)

        web_plot_path = UPLOAD_DIR / f"{session_id}_web.png"
        build_shmoo_plot(df, results, save_path=str(web_plot_path), as_base64=True)

        _sessions[session_id] = {
            "df": df,
            "preprocessor": preprocessor,
            "model": model,
            "meta": meta,
            "results": results,
            "save_path": str(save_path),
            "web_plot_path": str(web_plot_path),
            "filename": filename,
        }
    except ValueError as exc:
        save_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        save_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Shmoo analysis failed: {exc}") from exc

    return {
        "session_id": session_id,
        "filename": filename,
        "meta": meta,
        "results": serialize_results(results),
        "plot_url": f"/api/shmoo/plot/{session_id}.png",
    }


def plot_path_for(session_id: str) -> Path:
    web_plot_path = UPLOAD_DIR / f"{session_id}_web.png"
    if web_plot_path.exists():
        return web_plot_path

    session = get_session(session_id)
    build_shmoo_plot(
        session["df"],
        session["results"],
        save_path=str(web_plot_path),
        as_base64=True,
    )
    return web_plot_path


def generate_shmoo_report(session_id: str, text_mode: str = "template") -> Path:
    session = get_session(session_id)
    results = session["results"]
    meta = session["meta"]
    df = session["df"]

    # Template-only for this pass (LLM optional later)
    _ = text_mode
    narrative = TemplateEngine().generate(results, meta)

    plot_path = REPORT_DIR / f"{session_id}_plot.png"
    build_shmoo_plot(df, results, save_path=str(plot_path))

    report_path = REPORT_DIR / f"{session_id}_report.pdf"
    ReportGenerator().generate(
        results=results,
        meta=meta,
        narrative=narrative,
        plot_path=str(plot_path),
        output_path=str(report_path),
    )
    return report_path
