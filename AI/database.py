# ============================================================
# FILE: database.py
# ROLE: CareSync Database Layer
# PURPOSE:
#   All MySQL reads/writes used by the CareSync Patient Portal.
#
# IMPORTANT DATABASE STRUCTURE
#   patient
#       patient_id (primary key)
#       full_name
#       date_of_birth
#       gender
#       phone
#       email
#       address
#       blood_group
#       emergency_contact_name
#       emergency_contact_phone
#       is_deleted
#       created_at
#       updated_at
#
#   beds
#       id (primary key)
#       bed_number
#       ward
#       status
#
#   bed_assignments
#       id (primary key)
#       patient_id (foreign key -> patient.patient_id)
#       bed_id (foreign key -> beds.id)
#       nurse_name
#       assigned_at
#
#   patient_discharges
#       id (primary key)
#       patient_id (foreign key -> patient.patient_id)
#       bed_id
#       discharge_summary
#       discharged_at
#
# The reference project uses a different schema:
#   patients.id
#   beds.bed_id / is_occupied
#   staff_shifts.nurse_name
#   patients.status
#
# This file deliberately DOES NOT rename the CareSync schema.
# ============================================================

import os
from datetime import datetime
from typing import Optional

import mysql.connector

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# ============================================================
# DATABASE CONFIGURATION
# ============================================================

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "caresync")


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_connection():
    """Create and return a MySQL connection."""
    return mysql.connector.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        use_pure=True,
    )


# ============================================================
# INTERNAL HELPERS
# ============================================================

def row_to_dict(cursor, row):
    """Convert a MySQL tuple into a dictionary."""
    if row is None:
        return None

    return dict(zip(cursor.column_names, row))


def _close(cursor=None, connection=None):
    """Safely close a cursor and connection."""
    if cursor is not None:
        cursor.close()

    if connection is not None:
        connection.close()


# ============================================================
# PATIENT LOOKUP
# ============================================================

def get_patient(patient_id: int):
    """
    Return one non-deleted CareSync patient.

    Status is derived from the CareSync relationship tables:
        Admitted    -> active bed assignment exists
        Discharged  -> no active bed + discharge record exists
        Not Assigned -> neither exists
    """
    conn = None
    cur = None

    try:
        conn = get_connection()
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT
                p.patient_id,
                p.full_name,
                p.date_of_birth,
                p.gender,
                p.phone,
                p.email,
                p.address,
                p.blood_group,
                p.emergency_contact_name,
                p.emergency_contact_phone,
                p.is_deleted,
                p.created_at,
                p.updated_at,

                ba.id AS assignment_id,
                ba.bed_id,
                ba.nurse_name,
                ba.assigned_at,

                b.bed_number,
                b.ward,
                b.status AS bed_status,

                pd.id AS discharge_id,
                pd.discharge_summary,
                pd.discharged_at

            FROM patient p

            LEFT JOIN bed_assignments ba
                ON p.patient_id = ba.patient_id

            LEFT JOIN beds b
                ON ba.bed_id = b.id

            LEFT JOIN (
                SELECT pd1.*
                FROM patient_discharges pd1
                INNER JOIN (
                    SELECT
                        patient_id,
                        MAX(discharged_at) AS max_discharged_at
                    FROM patient_discharges
                    GROUP BY patient_id
                ) latest
                    ON latest.patient_id = pd1.patient_id
                   AND latest.max_discharged_at = pd1.discharged_at
            ) pd
                ON p.patient_id = pd.patient_id

            WHERE p.patient_id = %s
              AND p.is_deleted = 0

            ORDER BY ba.assigned_at DESC
            LIMIT 1
            """,
            (patient_id,),
        )

        row = cur.fetchone()

        if not row:
            return None

        if row.get("bed_id") is not None:
            row["status"] = "Admitted"
        elif row.get("discharge_id") is not None:
            row["status"] = "Discharged"
        else:
            row["status"] = "Not Assigned"

        return row

    finally:
        _close(cur, conn)


# ============================================================
# GET ALL PATIENTS
# ============================================================

def get_all_patients():
    """
    Return all non-deleted CareSync patients.

    This is the endpoint consumed by the frontend and matches
    the reference endpoint name /patients while preserving
    the CareSync patient_id/full_name fields.
    """
    conn = None
    cur = None

    try:
        conn = get_connection()
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT
                p.patient_id,
                p.full_name,
                p.date_of_birth,
                p.gender,
                p.phone,
                p.email,
                p.address,
                p.blood_group,
                p.emergency_contact_name,
                p.emergency_contact_phone,
                p.is_deleted,
                p.created_at,
                p.updated_at,

                ba.id AS assignment_id,
                ba.bed_id,
                ba.nurse_name,
                ba.assigned_at,

                b.bed_number,
                b.ward,
                b.status AS bed_status,

                pd.id AS discharge_id,
                pd.discharge_summary,
                pd.discharged_at

            FROM patient p

            LEFT JOIN bed_assignments ba
                ON p.patient_id = ba.patient_id

            LEFT JOIN beds b
                ON ba.bed_id = b.id

            LEFT JOIN (
                SELECT pd1.*
                FROM patient_discharges pd1
                INNER JOIN (
                    SELECT
                        patient_id,
                        MAX(discharged_at) AS max_discharged_at
                    FROM patient_discharges
                    GROUP BY patient_id
                ) latest
                    ON latest.patient_id = pd1.patient_id
                   AND latest.max_discharged_at = pd1.discharged_at
            ) pd
                ON p.patient_id = pd.patient_id

            WHERE p.is_deleted = 0

            ORDER BY p.patient_id ASC
            """
        )

        patients = cur.fetchall()

        for patient in patients:
            if patient.get("bed_id") is not None:
                patient["status"] = "Admitted"
            elif patient.get("discharge_id") is not None:
                patient["status"] = "Discharged"
            else:
                patient["status"] = "Not Assigned"

        return patients

    finally:
        _close(cur, conn)


# ============================================================
# BED AVAILABILITY
# ============================================================

def get_bed_availability():
    """
    Return every bed using the actual CareSync beds schema.
    """
    conn = None
    cur = None

    try:
        conn = get_connection()
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT
                id,
                bed_number,
                ward,
                status
            FROM beds
            ORDER BY ward ASC, bed_number ASC
            """
        )

        return cur.fetchall()

    finally:
        _close(cur, conn)


# ============================================================
# FIND AVAILABLE BED
# ============================================================

def find_empty_bed(ward: Optional[str] = None):
    """
    Find the first available bed.

    CareSync uses:
        beds.id
        beds.status = 'AVAILABLE'

    It does NOT use the reference project's:
        beds.bed_id
        beds.is_occupied
    """
    conn = None
    cur = None

    try:
        conn = get_connection()
        cur = conn.cursor(dictionary=True)

        if ward:
            cur.execute(
                """
                SELECT
                    id,
                    bed_number,
                    ward,
                    status
                FROM beds
                WHERE status = 'AVAILABLE'
                  AND ward = %s
                ORDER BY id ASC
                LIMIT 1
                """,
                (ward,),
            )
        else:
            cur.execute(
                """
                SELECT
                    id,
                    bed_number,
                    ward,
                    status
                FROM beds
                WHERE status = 'AVAILABLE'
                ORDER BY id ASC
                LIMIT 1
                """
            )

        return cur.fetchone()

    finally:
        _close(cur, conn)


# ============================================================
# ON-DUTY NURSE
# ============================================================

def get_on_duty_nurse(ward=None):
    """
    Return nurse information only when a confirmed CareSync
    staff_shifts schema is available.

    The supplied CareSync source does not establish a usable
    staff_shifts column layout, so this function intentionally
    returns None rather than guessing column names.
    """
    conn = None
    cur = None

    try:
        conn = get_connection()
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT COUNT(*) AS table_count
            FROM information_schema.tables
            WHERE table_schema = DATABASE()
              AND table_name = 'staff_shifts'
            """
        )

        result = cur.fetchone()

        if not result or result["table_count"] == 0:
            return None

        # A staff_shifts table may exist, but the supplied project
        # does not establish its actual columns. Do not guess them.
        return None

    except Exception as error:
        print("NURSE LOOKUP WARNING:", error)
        return None

    finally:
        _close(cur, conn)


# ============================================================
# ASSIGN BED TO PATIENT
# ============================================================

def assign_bed_to_patient(
    patient_id: int,
    bed_id: int,
    nurse_name: Optional[str] = None,
):
    """
    Atomically assign an available CareSync bed to a patient.

    Steps:
        1. Verify patient.
        2. Lock the requested bed.
        3. Verify the bed is AVAILABLE.
        4. Verify patient has no active assignment.
        5. Mark bed OCCUPIED.
        6. Insert bed_assignments row.
        7. Commit.
    """
    conn = None
    cur = None

    try:
        conn = get_connection()
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT
                patient_id,
                full_name
            FROM patient
            WHERE patient_id = %s
              AND is_deleted = 0
            """,
            (patient_id,),
        )

        patient = cur.fetchone()

        if not patient:
            raise ValueError(
                f"Patient {patient_id} does not exist."
            )

        cur.execute(
            """
            SELECT
                id,
                bed_number,
                ward,
                status
            FROM beds
            WHERE id = %s
            FOR UPDATE
            """,
            (bed_id,),
        )

        bed = cur.fetchone()

        if not bed:
            raise ValueError(
                f"Bed {bed_id} does not exist."
            )

        if str(bed["status"]).upper() != "AVAILABLE":
            raise ValueError(
                f"Bed {bed['bed_number']} is already occupied."
            )

        cur.execute(
            """
            SELECT
                ba.id,
                ba.bed_id,
                b.bed_number
            FROM bed_assignments ba
            INNER JOIN beds b
                ON ba.bed_id = b.id
            WHERE ba.patient_id = %s
            LIMIT 1
            FOR UPDATE
            """,
            (patient_id,),
        )

        existing_assignment = cur.fetchone()

        if existing_assignment:
            raise ValueError(
                f"Patient {patient_id} already has bed "
                f"{existing_assignment['bed_number']}."
            )

        cur.execute(
            """
            UPDATE beds
            SET status = 'OCCUPIED'
            WHERE id = %s
            """,
            (bed_id,),
        )

        cur.execute(
            """
            INSERT INTO bed_assignments
            (
                patient_id,
                bed_id,
                nurse_name
            )
            VALUES
            (
                %s,
                %s,
                %s
            )
            """,
            (
                patient_id,
                bed_id,
                nurse_name,
            ),
        )

        conn.commit()

        return {
            "success": True,
            "message": "Bed assigned successfully.",
            "patient_id": patient_id,
            "ward": bed["ward"],
            "bed_id": bed["id"],
            "bed_number": bed["bed_number"],
            "nurse": nurse_name,
            "assignment": {
                "status": "assigned",
                "message": "Patient has been assigned to the bed.",
            },
        }

    except Exception:
        if conn:
            conn.rollback()
        raise

    finally:
        _close(cur, conn)


# ============================================================
# DISCHARGE PATIENT
# ============================================================

def discharge_patient_db(
    patient_id: int,
    discharge_summary: str = "",
):
    """
    Discharge a CareSync patient.

    Steps:
        1. Verify patient.
        2. Lock/find the active bed assignment, if any.
        3. Reject a second discharge when no active assignment
           exists and a discharge record already exists.
        4. Insert patient_discharges.
        5. Release the bed.
        6. Delete the active bed assignment.
        7. Commit.
    """
    conn = None
    cur = None

    try:
        conn = get_connection()
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT
                patient_id,
                full_name
            FROM patient
            WHERE patient_id = %s
              AND is_deleted = 0
            """,
            (patient_id,),
        )

        patient = cur.fetchone()

        if not patient:
            raise ValueError(
                f"Patient {patient_id} does not exist."
            )

        cur.execute(
            """
            SELECT
                ba.id AS assignment_id,
                ba.bed_id,
                ba.nurse_name,
                b.bed_number,
                b.ward
            FROM bed_assignments ba
            INNER JOIN beds b
                ON ba.bed_id = b.id
            WHERE ba.patient_id = %s
            LIMIT 1
            FOR UPDATE
            """,
            (patient_id,),
        )

        assignment = cur.fetchone()

        cur.execute(
            """
            SELECT
                id
            FROM patient_discharges
            WHERE patient_id = %s
            ORDER BY discharged_at DESC
            LIMIT 1
            """,
            (patient_id,),
        )

        existing_discharge = cur.fetchone()

        if existing_discharge and not assignment:
            raise ValueError(
                f"Patient {patient_id} is already discharged."
            )

        bed_id = assignment["bed_id"] if assignment else None
        bed_number = assignment["bed_number"] if assignment else None
        ward = assignment["ward"] if assignment else None
        nurse_name = assignment["nurse_name"] if assignment else None

        cur.execute(
            """
            INSERT INTO patient_discharges
            (
                patient_id,
                bed_id,
                discharge_summary
            )
            VALUES
            (
                %s,
                %s,
                %s
            )
            """,
            (
                patient_id,
                bed_id,
                discharge_summary,
            ),
        )

        if bed_id is not None:
            cur.execute(
                """
                UPDATE beds
                SET status = 'AVAILABLE'
                WHERE id = %s
                """,
                (bed_id,),
            )

        cur.execute(
            """
            DELETE FROM bed_assignments
            WHERE patient_id = %s
            """,
            (patient_id,),
        )

        conn.commit()

        return {
            "success": True,
            "message": "Patient discharged successfully.",
            "patient_id": patient_id,
            "patient_name": patient["full_name"],
            "bed_id": bed_id,
            "bed_number": bed_number,
            "ward": ward,
            "nurse": nurse_name,
            "discharged_at": datetime.now().isoformat(),
        }

    except Exception:
        if conn:
            conn.rollback()
        raise

    finally:
        _close(cur, conn)


# ============================================================
# STATUS COMPATIBILITY FUNCTION
# ============================================================

def update_patient_status(patient_id: int, status: str):
    """
    Compatibility wrapper.

    The CareSync patient table has no status column in the
    supplied project. Status is derived from assignments and
    patient_discharges instead.
    """
    normalized = str(status).strip().lower()

    if normalized == "discharged":
        return discharge_patient_db(patient_id)

    patient = get_patient(patient_id)

    if not patient:
        raise ValueError(
            f"Patient {patient_id} does not exist."
        )

    return {
        "success": True,
        "message": (
            "Patient status is derived from CareSync "
            "bed/discharge records; no patient.status column "
            "was modified."
        ),
        "patient_id": patient_id,
        "status": patient["status"],
    }


# ============================================================
# TRIAGE DATA
# ============================================================

def triage_patient(patient_id: int):
    """
    Return the actual CareSync patient fields available for
    triage. Medical vitals/symptoms are not invented because
    they are not present in the supplied patient schema.
    """
    patient = get_patient(patient_id)

    if not patient:
        return None

    return {
        "patient_id": patient["patient_id"],
        "full_name": patient["full_name"],
        "date_of_birth": patient["date_of_birth"],
        "gender": patient["gender"],
        "blood_group": patient["blood_group"],
        "phone": patient["phone"],
        "email": patient["email"],
        "address": patient["address"],
        "emergency_contact_name": patient["emergency_contact_name"],
        "emergency_contact_phone": patient["emergency_contact_phone"],
        "status": patient["status"],
        "ward": patient.get("ward"),
        "bed_number": patient.get("bed_number"),
        "message": (
            "Patient information retrieved. Symptoms and vital "
            "signs are not stored in the supplied CareSync "
            "patient table."
        ),
    }


# ============================================================
# HEALTH CHECK
# ============================================================

def test_database_connection():
    """Test whether the configured CareSync MySQL database is reachable."""
    conn = None

    try:
        conn = get_connection()
        return {
            "success": True,
            "database": DB_NAME,
            "message": "Database connection successful.",
        }

    except Exception as error:
        return {
            "success": False,
            "database": DB_NAME,
            "message": str(error),
        }

    finally:
        if conn:
            conn.close()


# ============================================================
# STATUS-COMPATIBILITY LIST
# ============================================================

def get_patients_with_status():
    """Backward-compatible alias used by earlier CareSync code."""
    return get_all_patients()
