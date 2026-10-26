# ============================================================
# FILE: main.py
# ROLE: FastAPI server for CareSync Patient Portal
# RUN:
#     uvicorn main:app --reload
#
# Canonical endpoints:
#   GET  /patients
#   POST /triage/{patient_id}
#   POST /tools/check_bed
#   POST /tools/get_on_duty_nurse
#   POST /tools/assign_bed
#   POST /agent/assign_bed
#   GET  /beds/availability
#   POST /patients/{patient_id}/discharge
#
# Compatibility aliases are also kept for the old singular
# /patient routes so existing callers are not broken.
# ============================================================

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from database import (
    get_patient,
    get_all_patients,
    get_bed_availability,
)

from triage_ai import run_triage

from mcp_tools import (
    tool_check_bed,
    tool_get_on_duty_nurse,
    tool_assign_bed,
)

from bed_agent import run_agent

from discharge import DischargeManager

from exceptions import (
    AlreadyDischargedError,
    CriticalPatientError,
)


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="CareSync Patient Portal API",
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# HOME PAGE
# ============================================================

@app.get("/")
def serve_homepage():
    """Serve the CareSync frontend."""
    return FileResponse("index.html")


# ============================================================
# PATIENT API
# ============================================================

@app.get("/patients")
def list_patients():
    """
    Canonical patient-list endpoint.

    Uses the CareSync singular table `patient` internally but
    keeps the reference-compatible plural HTTP endpoint.
    """
    return get_all_patients()


@app.get("/patient")
def list_patients_legacy():
    """
    Backward-compatible alias for the old CareSync endpoint.

    New frontend/API calls should use /patients.
    """
    return get_all_patients()


# ============================================================
# BED AVAILABILITY
# ============================================================

@app.get("/beds/availability")
def list_bed_availability():
    """
    Return all beds for the CareSync bed-availability UI.

    Response shape:
        {
            "success": true,
            "beds": [...]
        }
    """
    return {
        "success": True,
        "beds": get_bed_availability(),
    }


# ============================================================
# AI TRIAGE
# ============================================================

@app.post("/triage/{patient_id}")
def do_triage(patient_id: int):
    """
    Run AI triage for a CareSync patient.

    Response keeps the reference-compatible `result` field
    while also exposing the actual CareSync patient data for
    the current CareSync frontend.
    """

    patient = get_patient(patient_id)

    if not patient:
        raise HTTPException(
            status_code=404,
            detail="Patient not found",
        )

    try:
        result = run_triage(patient)
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Triage failed: {error}",
        )

    return {
        "success": True,
        "patient_id": patient_id,
        "patient": patient,
        "triage": {
            "message": result,
        },
        "result": result,
    }


# ============================================================
# REQUEST MODELS
# ============================================================

class BedRequest(BaseModel):
    ward: str


class NurseRequest(BaseModel):
    ward: str


class AssignRequest(BaseModel):
    patient_id: int
    bed_id: int
    nurse_name: str | None = None


class AgentRequest(BaseModel):
    patient_id: int
    ward: str


# ============================================================
# MCP TOOL: CHECK EMPTY BED
# ============================================================

@app.post("/tools/check_bed")
def api_check_bed(req: BedRequest):
    """Find an available CareSync bed in a ward."""
    try:
        return tool_check_bed(req.ward)
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        )


# ============================================================
# MCP TOOL: GET ON-DUTY NURSE
# ============================================================

@app.post("/tools/get_on_duty_nurse")
def api_get_nurse(req: NurseRequest):
    """Find an on-duty nurse when the CareSync schema supports it."""
    try:
        return tool_get_on_duty_nurse(req.ward)
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        )


# ============================================================
# MCP TOOL: ASSIGN BED
# ============================================================

@app.post("/tools/assign_bed")
def api_assign_bed(req: AssignRequest):
    """
    Manually assign a CareSync patient to a selected bed.
    """
    try:
        result = tool_assign_bed(
            req.patient_id,
            req.bed_id,
            req.nurse_name,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        )

    if not result.get("success"):
        raise HTTPException(
            status_code=400,
            detail=result.get(
                "message",
                "Bed assignment failed.",
            ),
        )

    return result


# ============================================================
# AI / AUTOMATIC BED AGENT
# ============================================================

@app.post("/agent/assign_bed")
def agent_assign_bed(req: AgentRequest):
    """
    Run the CareSync automatic bed-assignment workflow.

    The result remains under `result`, matching the reference
    response contract, while `success` and `message` are also
    exposed for the current CareSync frontend.
    """
    result = run_agent(
        req.patient_id,
        req.ward,
    )

    return {
        "success": bool(result.get("success")),
        "message": result.get(
            "message",
            "Bed assignment completed.",
        ),
        "result": result,
    }


# ============================================================
# DISCHARGE MANAGER
# ============================================================

discharge_manager = DischargeManager()


# ============================================================
# PATIENT DISCHARGE
# ============================================================

def _perform_discharge(patient_id: int):
    """Shared implementation for canonical and legacy routes."""
    try:
        summary = discharge_manager.discharge_patient(
            patient_id
        )

        return {
            "success": True,
            "patient_id": patient_id,
            "summary": summary,
            "message": "Patient discharged successfully.",
        }

    except AlreadyDischargedError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        )

    except CriticalPatientError as error:
        # Kept for compatibility with the reference exception
        # contract. The supplied CareSync schema has no critical
        # vital columns, so the current discharge manager does not
        # raise this exception.
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    except ValueError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected discharge error: {error}",
        )


@app.post("/patients/{patient_id}/discharge")
def discharge_patient(patient_id: int):
    """
    Canonical reference-compatible discharge endpoint.
    """
    return _perform_discharge(patient_id)


@app.post("/patient/{patient_id}/discharge")
def discharge_patient_legacy(patient_id: int):
    """
    Backward-compatible alias for the previous singular route.
    """
    return _perform_discharge(patient_id)
