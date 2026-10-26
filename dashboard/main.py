
# main.py
# CareSync Pro Dashboard Backend

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
import mysql.connector

# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(title="CareSync Pro Dashboard API")


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# ============================================================
# DATABASE CONNECTION
# ============================================================


def get_db():
    db_password = os.getenv("DB_PASSWORD")
    if not db_password:
        raise RuntimeError(
            "DB_PASSWORD is not configured. Set it in your environment."
        )

    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=db_password,
        database=os.getenv("DB_NAME", "caresync"),
        use_pure=True
    )


# ============================================================
# ENDPOINT 1: SUMMARY
# ============================================================

@app.get("/summary")
def get_summary():

    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:

        # Patients
        cursor.execute(
            "SELECT COUNT(*) AS total "
            "FROM patient "
            "WHERE is_deleted = 0"
        )
        patients = cursor.fetchone()["total"]

        # Doctors
        cursor.execute(
            "SELECT COUNT(*) AS total "
            "FROM doctor "
            "WHERE is_active = 1"
        )
        doctors = cursor.fetchone()["total"]

        # Appointments
        cursor.execute(
            "SELECT COUNT(*) AS total "
            "FROM appointment"
        )
        appointments = cursor.fetchone()["total"]

        # Bills
        cursor.execute(
            "SELECT COUNT(*) AS total "
            "FROM billing"
        )
        bills = cursor.fetchone()["total"]

        # Rejected bills
        cursor.execute(
            "SELECT COUNT(*) AS total "
            "FROM billing "
            "WHERE status = 'Rejected'"
        )
        rejected = cursor.fetchone()["total"]

        # Rejection rate
        rejection_rate = (
            round((rejected / bills) * 100, 1)
            if bills > 0
            else 0
        )

        # Revenue
        cursor.execute(
            "SELECT ROUND(SUM(amount_paid), 2) AS total "
            "FROM billing"
        )
        revenue = cursor.fetchone()["total"] or 0

        # Prescriptions
        cursor.execute(
            "SELECT COUNT(*) AS total "
            "FROM prescription "
            "WHERE is_deleted = 0"
        )
        prescriptions = cursor.fetchone()["total"]

        # Notifications
        cursor.execute(
            "SELECT COUNT(*) AS total "
            "FROM notification "
            "WHERE is_read = 0"
        )
        unread_notifications = cursor.fetchone()["total"]

        # Reports
        cursor.execute(
            "SELECT COUNT(*) AS total "
            "FROM report "
            "WHERE is_deleted = 0"
        )
        reports = cursor.fetchone()["total"]

        return {
            "total_patients": patients,
            "total_doctors": doctors,
            "total_appointments": appointments,
            "total_bills": bills,
            "rejection_rate": rejection_rate,
            "total_revenue": float(revenue),
            "total_prescriptions": prescriptions,
            "unread_notifications": unread_notifications,
            "total_reports": reports
        }

    finally:
        cursor.close()
        db.close()


# ============================================================
# ENDPOINT 2: PATIENTS
# ============================================================

@app.get("/patients")
def get_patients(search: str = ""):
    """
    Return up to 50 patients (newest first).

    Optional ?search=<text> matches part of the patient's name
    across ALL patients, not just the 50 newest.
    """

    term = (search or "").strip()[:100]

    where = "is_deleted = 0"
    params = ()

    if term:
        # '|' is the LIKE escape character, so a typed % or _
        # is matched literally instead of acting as a wildcard.
        escaped = (
            term.replace("|", "||")
                .replace("%", "|%")
                .replace("_", "|_")
        )
        where += " AND full_name LIKE %s ESCAPE '|'"
        params = (f"%{escaped}%",)

    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:

        cursor.execute(
            f"""
            SELECT
                patient_id,
                full_name,
                gender,
                blood_group,
                DATE_FORMAT(date_of_birth, '%d %b %Y') AS date_of_birth,
                DATE_FORMAT(created_at, '%d %b %Y') AS registered_on
            FROM patient
            WHERE {where}
            ORDER BY created_at DESC
            LIMIT 50
            """,
            params,
        )

        patients = cursor.fetchall()

        return {
            "patients": patients,
            "search": term,
        }

    finally:
        cursor.close()
        db.close()


# ============================================================
# ENDPOINT 3: BILLING
# ============================================================

@app.get("/billing")
def get_billing():

    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:

        cursor.execute(
            """
            SELECT
                b.bill_id,
                p.full_name AS patient_name,
                b.total_amount,
                b.amount_paid,
                b.status,
                DATE_FORMAT(b.bill_date, '%d %b %Y') AS bill_date
            FROM billing b
            JOIN patient p
                ON p.patient_id = b.patient_id
            ORDER BY b.created_at DESC
            LIMIT 50
            """
        )

        bills = cursor.fetchall()

        for bill in bills:

            if bill["total_amount"] is not None:
                bill["total_amount"] = float(
                    bill["total_amount"]
                )

            if bill["amount_paid"] is not None:
                bill["amount_paid"] = float(
                    bill["amount_paid"]
                )

        return {
            "bills": bills
        }

    finally:
        cursor.close()
        db.close()


# ============================================================
# ENDPOINT 4: DOCTORS
# ============================================================

@app.get("/doctors")
def get_doctors():

    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:

        cursor.execute(
            """
            SELECT
                d.doctor_id,
                d.full_name,
                d.specialisation,
                COUNT(a.appointment_id) AS total_appointments
            FROM doctor d

            LEFT JOIN appointment a
                ON a.doctor_id = d.doctor_id
                AND a.status = 'Completed'

            WHERE d.is_active = 1

            GROUP BY
                d.doctor_id,
                d.full_name,
                d.specialisation

            ORDER BY total_appointments DESC
            """
        )

        doctors = cursor.fetchall()

        return {
            "doctors": doctors
        }

    finally:
        cursor.close()
        db.close()


# ============================================================
# ENDPOINT 5: PRESCRIPTIONS
# ============================================================

@app.get("/prescriptions")
def get_prescriptions():

    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:

        cursor.execute(
            """
            SELECT
                pr.prescription_id,
                p.full_name AS patient_name,
                d.full_name AS doctor_name,
                pr.medicine_name,
                pr.dosage,
                pr.frequency,
                pr.duration_days,
                DATE_FORMAT(
                    pr.created_at,
                    '%d %b %Y'
                ) AS prescribed_on

            FROM prescription pr

            JOIN patient p
                ON p.patient_id = pr.patient_id

            JOIN doctor d
                ON d.doctor_id = pr.doctor_id

            WHERE pr.is_deleted = 0

            ORDER BY pr.created_at DESC

            LIMIT 50
            """
        )

        prescriptions = cursor.fetchall()

        return {
            "prescriptions": prescriptions
        }

    finally:
        cursor.close()
        db.close()


# ============================================================
# ENDPOINT 6: NOTIFICATIONS
# ============================================================

@app.get("/notifications")
def get_notifications():

    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:

        cursor.execute(
            """
            SELECT
                notification_id,
                user_type,
                user_id,
                title,
                message,
                is_read,
                DATE_FORMAT(
                    created_at,
                    '%d %b %Y %H:%i'
                ) AS created_on

            FROM notification

            ORDER BY
                is_read ASC,
                created_at DESC

            LIMIT 50
            """
        )

        notifications = cursor.fetchall()

        return {
            "notifications": notifications
        }

    finally:
        cursor.close()
        db.close()


# ============================================================
# ENDPOINT 7: REPORTS
# ============================================================

@app.get("/reports")
def get_reports():

    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:

        cursor.execute(
            """
            SELECT
                r.report_id,
                p.full_name AS patient_name,
                r.report_type,
                r.file_path,
                d.full_name AS generated_by_doctor,
                DATE_FORMAT(
                    r.created_at,
                    '%d %b %Y'
                ) AS generated_on

            FROM report r

            JOIN patient p
                ON p.patient_id = r.patient_id

            LEFT JOIN doctor d
                ON d.doctor_id = r.generated_by

            WHERE r.is_deleted = 0

            ORDER BY r.created_at DESC

            LIMIT 50
            """
        )

        reports = cursor.fetchall()

        return {
            "reports": reports
        }

    finally:
        cursor.close()
        db.close()


# ============================================================
# ENDPOINT 8: ACTIVITY LOG
# ============================================================

@app.get("/activity-log")
def get_activity_log():

    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:

        cursor.execute(
            """
            SELECT
                log_id,
                user_type,
                user_id,
                action,
                target_table,
                target_id,
                ip_address,
                DATE_FORMAT(
                    logged_at,
                    '%d %b %Y %H:%i'
                ) AS logged_on

            FROM activity_log

            ORDER BY logged_at DESC

            LIMIT 100
            """
        )

        logs = cursor.fetchall()

        return {
            "activity_log": logs
        }

    finally:
        cursor.close()
        db.close()


# ============================================================
# ENDPOINT 9: DOCTOR ANALYTICS
# ============================================================

@app.get("/analytics/doctors")
def get_doctor_analytics():

    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:

        cursor.execute(
            """
            SELECT
                d.doctor_id,
                d.full_name,
                d.specialisation,

                COUNT(
                    CASE
                        WHEN a.status = 'Completed'
                        THEN a.appointment_id
                    END
                ) AS completed_appointments,

                COUNT(
                    CASE
                        WHEN a.status = 'Scheduled'
                        THEN a.appointment_id
                    END
                ) AS scheduled_appointments,

                COUNT(
                    CASE
                        WHEN a.status = 'Cancelled'
                        THEN a.appointment_id
                    END
                ) AS cancelled_appointments,

                COUNT(a.appointment_id)
                    AS total_appointments

            FROM doctor d

            LEFT JOIN appointment a
                ON a.doctor_id = d.doctor_id

            WHERE d.is_active = 1

            GROUP BY
                d.doctor_id,
                d.full_name,
                d.specialisation

            ORDER BY total_appointments DESC
            """
        )

        analytics = cursor.fetchall()

        return {
            "doctors": analytics
        }

    finally:
        cursor.close()
        db.close()


# ============================================================
# ENDPOINT 10: DOCTOR SUMMARY (used by dashboard.html chart)
# Same real data as /analytics/doctors, under the key the
# frontend reads (doctor_summary).
# ============================================================

@app.get("/doctor-summary")
def get_doctor_summary():

    return {
        "doctor_summary": get_doctor_analytics()["doctors"]
    }


# ============================================================
# ROOT / HEALTH CHECK
# ============================================================

@app.get("/")
def root():

    return {
        "success": True,
        "message": "CareSync Pro Dashboard API is running",
        "database": "caresync"
    }