# ============================================================
# FILE: discharge.py
# PURPOSE: CareSync patient discharge management
# ============================================================

from datetime import datetime
from pathlib import Path

from database import (
    get_patient,
    discharge_patient_db,
)

from exceptions import AlreadyDischargedError


class DischargeManager:
    """
    Generates a discharge summary and commits the discharge
    through the CareSync database layer.

    The reference project updates patients.status. CareSync
    does not have that column; discharge state is represented
    by patient_discharges plus removal of the active
    bed_assignments row and release of the bed.
    """

    def __init__(
        self,
        summary_directory="discharge_summaries",
    ):
        self.summary_directory = Path(summary_directory)
        self.summary_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

    # ========================================================
    # DISCHARGE PATIENT
    # ========================================================

    def discharge_patient(self, patient_id):
        """
        Discharge one CareSync patient.

        Returns:
            Complete discharge summary text.

        Raises:
            ValueError:
                Patient does not exist.

            AlreadyDischargedError:
                Patient already has a discharge record and no
                active bed assignment.
        """

        patient = get_patient(patient_id)

        if not patient:
            raise ValueError(
                f"Patient with ID {patient_id} does not exist."
            )

        if str(patient.get("status", "")).lower() == "discharged":
            patient_name = patient.get(
                "full_name",
                f"Patient {patient_id}",
            )
            raise AlreadyDischargedError(
                f"Patient {patient_name} is already discharged from hospital."
            )

        summary = self._generate_summary(patient)

        # The database operation is the authoritative commit.
        # It inserts patient_discharges, releases the bed and
        # removes the active assignment in one transaction.
        result = discharge_patient_db(
            patient_id=patient_id,
            discharge_summary=summary,
        )

        if not result or not result.get("success"):
            raise RuntimeError(
                "Patient discharge could not be committed to the database."
            )

        self._save_summary(
            patient_id,
            summary,
        )

        return summary

    # ========================================================
    # GENERATE SUMMARY
    # ========================================================

    @staticmethod
    def _generate_summary(patient):
        """Generate a summary using only real CareSync fields."""

        discharge_time = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        patient_id = patient.get(
            "patient_id",
            "N/A",
        )

        patient_name = patient.get(
            "full_name",
            "N/A",
        )

        date_of_birth = patient.get(
            "date_of_birth",
            "N/A",
        )

        gender = patient.get(
            "gender",
            "N/A",
        )

        blood_group = patient.get(
            "blood_group",
            "N/A",
        )

        phone = patient.get(
            "phone",
            "N/A",
        )

        email = patient.get(
            "email",
            "N/A",
        )

        ward = patient.get(
            "ward",
            "N/A",
        )

        bed_number = patient.get(
            "bed_number",
            "N/A",
        )

        nurse_name = patient.get(
            "nurse_name",
            "N/A",
        )

        summary = f"""
========================================
       HOSPITAL DISCHARGE SUMMARY
========================================

Patient ID       : {patient_id}
Patient Name     : {patient_name}
Date of Birth    : {date_of_birth}
Gender           : {gender}
Blood Group      : {blood_group}
Phone            : {phone}
Email            : {email}

Ward             : {ward}
Bed Number       : {bed_number}
Nurse            : {nurse_name}

Status           : DISCHARGED
Discharge Time   : {discharge_time}

----------------------------------------
Patient has been discharged successfully.
----------------------------------------
"""

        return summary.strip()

    # ========================================================
    # SAVE SUMMARY
    # ========================================================

    def _save_summary(self, patient_id, summary):
        """Save the generated summary as patient_<id>_discharge.txt."""

        filename = (
            self.summary_directory
            / f"patient_{patient_id}_discharge.txt"
        )

        filename.write_text(
            summary,
            encoding="utf-8",
        )

        return filename
