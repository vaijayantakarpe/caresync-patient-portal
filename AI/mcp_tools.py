# ============================================================
# FILE: mcp_tools.py
# ROLE: CareSync MCP-style database tools
#
# These functions are used both by FastAPI endpoints and by the
# CareSync bed-assignment agent.
#
# IMPORTANT:
# The reference project uses different bed/staff columns.
# CareSync uses:
#   beds.id
#   beds.bed_number
#   beds.ward
#   beds.status
#   bed_assignments.patient_id
#   bed_assignments.bed_id
#   bed_assignments.nurse_name
# ============================================================

from database import (
    find_empty_bed,
    get_on_duty_nurse,
    assign_bed_to_patient,
)


# ============================================================
# TOOL 1: CHECK AVAILABLE BED
# ============================================================

def tool_check_bed(ward: str) -> dict:
    """Find the first AVAILABLE bed in the requested ward."""
    try:
        bed = find_empty_bed(ward)

        if bed is None:
            return {
                "success": False,
                "status": "no_bed",
                "message": (
                    f"No empty beds available in "
                    f"{ward} ward right now."
                ),
            }

        bed_id = bed.get("id")

        if bed_id is None:
            return {
                "success": False,
                "status": "error",
                "message": (
                    "An available bed was found, but its "
                    "database ID is missing."
                ),
            }

        return {
            "success": True,
            "status": "found",
            "bed_id": bed_id,
            "bed_number": bed.get("bed_number"),
            "ward": bed.get("ward", ward),
            "status_value": bed.get("status", "AVAILABLE"),
        }

    except Exception as error:
        raise RuntimeError(
            f"Bed availability check failed: {error}"
        )


# ============================================================
# TOOL 2: GET ON-DUTY NURSE
# ============================================================

def tool_get_on_duty_nurse(ward: str) -> dict:
    """
    Look up an on-duty nurse when the database provides a
    confirmed staff schema.

    The supplied CareSync schema does not establish usable
    staff_shifts columns, so a missing nurse is represented
    explicitly rather than guessed.
    """
    try:
        nurse = get_on_duty_nurse(ward)

        if nurse is None:
            return {
                "success": False,
                "status": "no_nurse",
                "message": (
                    f"No confirmed on-duty nurse record is "
                    f"available for {ward} ward."
                ),
                "nurse_name": None,
                "ward": ward,
            }

        nurse_name = (
            nurse.get("staff_name")
            or nurse.get("nurse_name")
            or nurse.get("name")
        )

        if not nurse_name:
            return {
                "success": False,
                "status": "error",
                "message": "Nurse record has no usable name.",
                "nurse_name": None,
                "ward": ward,
            }

        return {
            "success": True,
            "status": "found",
            "nurse_id": nurse.get("id"),
            "nurse_name": nurse_name,
            "ward": nurse.get("ward", ward),
            "status_value": nurse.get("status"),
        }

    except Exception as error:
        raise RuntimeError(
            f"On-duty nurse lookup failed: {error}"
        )


# ============================================================
# TOOL 3: ASSIGN BED
# ============================================================

def tool_assign_bed(
    patient_id: int,
    bed_id: int,
    nurse_name: str | None = None,
) -> dict:
    """Assign the selected CareSync patient to the selected bed."""
    try:
        result = assign_bed_to_patient(
            patient_id=patient_id,
            bed_id=bed_id,
            nurse_name=nurse_name,
        )

        if isinstance(result, dict):
            return {
                "success": bool(result.get("success", True)),
                "status": "assigned",
                "message": (
                    result.get("message")
                    or f"Patient {patient_id} assigned "
                       f"to bed {bed_id}."
                ),
                "patient_id": patient_id,
                "bed_id": bed_id,
                "nurse_assigned": nurse_name,
                "assigned_by": "ai_agent",
                "assignment": result,
            }

        if result is True:
            return {
                "success": True,
                "status": "assigned",
                "message": (
                    f"Patient {patient_id} assigned "
                    f"to bed {bed_id}."
                ),
                "patient_id": patient_id,
                "bed_id": bed_id,
                "nurse_assigned": nurse_name,
                "assigned_by": "ai_agent",
            }

        return {
            "success": False,
            "status": "error",
            "message": "Database operation failed. Could not assign bed.",
            "patient_id": patient_id,
            "bed_id": bed_id,
        }

    except Exception as error:
        raise RuntimeError(
            f"Bed assignment failed: {error}"
        )
