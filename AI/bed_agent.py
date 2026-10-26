# ============================================================
# FILE: bed_agent.py
# PURPOSE: CareSync automatic bed-assignment agent
#
# The reference project uses Groq tool-calling to decide which
# MCP tool to invoke. The CareSync project already has direct
# Python MCP-style functions that operate on the real CareSync
# schema, so this agent keeps the same functional workflow
# without inventing a nurse or database column.
#
# Workflow:
#   1. Check an available bed.
#   2. Look for an on-duty nurse.
#   3. Assign the patient to the available bed.
#   4. Return a structured result for the frontend.
# ============================================================

from database import get_patient

from mcp_tools import (
    tool_check_bed,
    tool_get_on_duty_nurse,
    tool_assign_bed,
)


# ============================================================
# MAIN AGENT
# ============================================================

def run_agent(patient_id: int, ward: str):
    """
    Automatically assign a CareSync patient to an available bed.

    A nurse is optional because the supplied CareSync schema
    does not establish a usable staff_shifts schema. The actual
    bed assignment is always performed against the CareSync
    database.
    """

    ward = (ward or "").strip()

    if not ward:
        return {
            "success": False,
            "message": "Ward is required.",
            "patient_id": patient_id,
            "ward": ward,
        }

    # --------------------------------------------------------
    # STEP 1: CHECK WHETHER PATIENT IS ALREADY ASSIGNED
    # --------------------------------------------------------

    try:
        patient = get_patient(patient_id)
    except Exception as error:
        return {
            "success": False,
            "message": f"Unable to read patient assignment: {error}",
            "patient_id": patient_id,
            "ward": ward,
        }

    if not patient:
        return {
            "success": False,
            "message": f"Patient {patient_id} was not found.",
            "patient_id": patient_id,
            "ward": ward,
        }

    # Re-running automatic assignment for an already admitted
    # patient is an idempotent operation, not an error.
    if patient.get("bed_id") is not None:
        return {
            "success": True,
            "already_assigned": True,
            "message": (
                f"Patient {patient_id} is already assigned to "
                f"bed {patient.get('bed_number') or patient.get('bed_id')}."
            ),
            "patient_id": patient_id,
            "patient_name": patient.get("full_name"),
            "ward": patient.get("ward") or ward,
            "bed_id": patient.get("bed_id"),
            "bed_number": patient.get("bed_number"),
            "nurse": patient.get("nurse_name"),
            "status": "already_assigned",
        }

    # --------------------------------------------------------
    # STEP 2: CHECK AVAILABLE BED
    # --------------------------------------------------------

    try:
        bed_result = tool_check_bed(ward)
    except Exception as error:
        return {
            "success": False,
            "message": f"Unable to check bed availability: {error}",
            "patient_id": patient_id,
            "ward": ward,
        }

    if not bed_result.get("success"):
        return {
            "success": False,
            "message": bed_result.get(
                "message",
                "No available bed found.",
            ),
            "patient_id": patient_id,
            "ward": ward,
            "bed_result": bed_result,
        }

    bed_id = bed_result.get("bed_id")

    if bed_id is None:
        return {
            "success": False,
            "message": "Available bed has no database ID.",
            "patient_id": patient_id,
            "ward": ward,
            "bed_result": bed_result,
        }

    # --------------------------------------------------------
    # STEP 3: LOOK FOR ON-DUTY NURSE
    # --------------------------------------------------------

    try:
        nurse_result = tool_get_on_duty_nurse(ward)
    except Exception as error:
        nurse_result = {
            "success": False,
            "status": "error",
            "message": str(error),
            "nurse_name": None,
            "ward": ward,
        }

    nurse_name = nurse_result.get("nurse_name")

    # --------------------------------------------------------
    # STEP 4: ASSIGN BED
    # --------------------------------------------------------

    try:
        assignment = tool_assign_bed(
            patient_id=patient_id,
            bed_id=bed_id,
            nurse_name=nurse_name,
        )
    except Exception as error:
        return {
            "success": False,
            "message": f"Unable to assign bed: {error}",
            "patient_id": patient_id,
            "ward": ward,
            "bed_id": bed_id,
            "nurse": nurse_name,
        }

    if not assignment.get("success"):
        return {
            "success": False,
            "message": assignment.get(
                "message",
                "Bed assignment failed.",
            ),
            "patient_id": patient_id,
            "ward": ward,
            "bed_id": bed_id,
            "nurse": nurse_name,
            "assignment": assignment,
        }

    # --------------------------------------------------------
    # STEP 5: RETURN SUCCESS
    # --------------------------------------------------------

    return {
        "success": True,
        "message": "Bed assigned successfully.",
        "patient_id": patient_id,
        "ward": ward,
        "bed_id": bed_id,
        "bed_number": bed_result.get("bed_number"),
        "nurse": nurse_name,
        "nurse_status": nurse_result.get("status"),
        "assignment": assignment,
    }
