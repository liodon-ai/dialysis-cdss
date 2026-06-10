"""
Dialysis CDSS — FastAPI backend
Serves REST API + static frontend from a single process.
"""

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.database import init_db, log_deviation, save_session, get_deviations, get_sessions
from backend.models import PatientInput, DeviationInput, OVERRIDE_REASONS
from backend.protocol_runner import load_protocols, run_protocols

PROTOCOL_DIR = Path(__file__).parent.parent / "protocols"
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

app = FastAPI(title="Dialysis CDSS", version="0.1.0")

# ── startup ──────────────────────────────────────────────────────────────────

@app.on_event("startup")
def startup():
    init_db()


def _protocols():
    return load_protocols(str(PROTOCOL_DIR))


# ── API routes ────────────────────────────────────────────────────────────────

@app.post("/api/evaluate")
def evaluate(patient: PatientInput):
    """Run all protocols against the submitted labs. Saves the session."""
    protocols = _protocols()
    # Convert Pydantic models to plain dicts, dropping None values
    lab_dict  = {k: v for k, v in patient.labs.model_dump().items() if v is not None}
    meds_dict = {k: v for k, v in patient.current_medications.model_dump().items() if v is not None}
    payload   = {
        "patient_id": patient.patient_id,
        "session_date": patient.session_date,
        "labs": lab_dict,
        "current_medications": meds_dict,
    }
    recs = run_protocols(payload, protocols)
    save_session(patient.patient_id, patient.session_date, payload, recs)
    return {
        "patient_id":      patient.patient_id,
        "patient_name":    patient.patient_name,
        "session_date":    patient.session_date,
        "labs":            lab_dict,
        "prior_labs":      patient.prior_labs.model_dump() if patient.prior_labs else None,
        "current_medications": meds_dict,
        "recommendations": recs,
    }


@app.post("/api/deviations")
def record_deviation(dev: DeviationInput):
    """Log a clinician override of a protocol recommendation."""
    if dev.override_reason not in OVERRIDE_REASONS:
        raise HTTPException(status_code=422, detail=f"Unknown override reason: {dev.override_reason}")
    row_id = log_deviation(
        patient_id=dev.patient_id,
        session_date=dev.session_date,
        rule_id=dev.rule_id,
        protocol=dev.protocol,
        rule_name=dev.rule_name,
        recommended=dev.recommended,
        ordered=dev.ordered,
        override_reason=dev.override_reason,
        clinician_note=dev.clinician_note,
    )
    return {"status": "logged", "deviation_id": row_id}


@app.get("/api/deviations")
def list_deviations(patient_id: str | None = None, limit: int = 200):
    return get_deviations(patient_id=patient_id, limit=limit)


@app.get("/api/sessions/{patient_id}")
def patient_sessions(patient_id: str, limit: int = 12):
    return get_sessions(patient_id=patient_id, limit=limit)


@app.get("/api/override-reasons")
def override_reasons():
    return OVERRIDE_REASONS


@app.get("/api/protocols")
def list_protocols():
    """Return loaded protocol metadata (names, rule counts) — not the full rules."""
    protocols = _protocols()
    return {
        name: {"rule_count": len(p.get("rules", [])), "version": p.get("version", "?")}
        for name, p in protocols.items()
    }


@app.get("/api/health")
def health():
    return {"status": "ok"}


# ── frontend ──────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def index():
    return (FRONTEND_DIR / "index.html").read_text()


# Static assets (CSS, JS files if ever split out)
if (FRONTEND_DIR / "static").exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR / "static")), name="static")
