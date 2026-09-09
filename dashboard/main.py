# main.py
# CareSync Pro Dashboard Backend

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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
    allow_methods=["GET"],
    allow_headers=["*"],
)


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_db():
    return mysql.connector.connect(
        host="127.0.0.1",
        port=3306,
        user="root",
        password="Admin",
        database="caresync_pro",
        use_pure=True
    )


# ============================================================
# 1. SUMMARY
# ============================================================

@app.get("/summary")
def get_summary():

    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM patient
            WHERE is_deleted = 0
            """
        )
        patients = cursor.fetchone()["total"]

        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM doctor
            WHERE is_active = 1
            """
        )
        doctors = cursor.fetchone()["total"]

        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM appointment
            """
        )
        appointments = cursor.fetchone()["total"]

        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM billing
            """
        )
        bills = cursor.fetchone()["total"]

        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM billing
            WHERE status = 'Rejected'
            """
        )
        rejected = cursor.fetchone()["total"]

        rejection_rate = (
            round((rejected / bills) * 100, 1)
            if bills > 0
            else 0
        )

        cursor.execute(
            """
            SELECT ROUND(SUM(amount_paid), 2) AS total
            FROM billing
            """
        )
        revenue = cursor.fetchone()["total"] or 0

        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM prescription
            WHERE is_deleted = 0
            """
        )
        prescriptions = cursor.fetchone()["total"]

        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM notification
            WHERE is_read = 0
            """
        )
        unread_notifications = cursor.fetchone()["total"]

        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM report
            WHERE is_deleted = 0
            """
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
# 2. PATIENT LIST
# ============================================================

@app.get("/patients")
def get_patients():

    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT
                patient_id,
                full_name,
                gender,
                blood_group,
                DATE_FORMAT(
                    date_of_birth,
                    '%d %b %Y'
                ) AS date_of_birth,
                DATE_FORMAT(
                    created_at,
                    '%d %b %Y'
                ) AS registered_on
            FROM patient
            WHERE is_deleted = 0
            ORDER BY created_at DESC
            LIMIT 50
            """
        )

        patients = cursor.fetchall()

        return {
            "patients": patients
        }

    finally:
        cursor.close()
        db.close()


# ============================================================
# 3. PATIENT LOOKUP BY ID
# ============================================================

@app.get("/patients/{patient_id}")
def get_patient(patient_id: int):

    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT
                patient_id,
                full_name,
                blood_group,
                email
            FROM patient
            WHERE patient_id = %s
              AND is_deleted = 0
            """,
            (patient_id,)
        )

        patient = cursor.fetchone()

        if patient is None:
            raise HTTPException(
                status_code=404,
                detail="Patient not found"
            )

        return patient

    finally:
        cursor.close()
        db.close()


# ============================================================
# 4. BILLING
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
                DATE_FORMAT(
                    b.bill_date,
                    '%d %b %Y'
                ) AS bill_date
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
# 5. DOCTORS
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
# 6. DOCTOR ANALYTICS
# ============================================================

@app.get("/analytics/doctors")
def get_doctor_analytics():

    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT
                d.full_name AS doctor_name,
                COUNT(a.appointment_id) AS total_appointments
            FROM doctor d
            LEFT JOIN appointment a
                ON a.doctor_id = d.doctor_id
                AND a.status = 'Completed'
            WHERE d.is_active = 1
            GROUP BY
                d.doctor_id,
                d.full_name
            ORDER BY total_appointments DESC
            """
        )

        analytics = cursor.fetchall()

        return analytics

    finally:
        cursor.close()
        db.close()


# ============================================================
# 7. PRESCRIPTIONS
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
# 8. NOTIFICATIONS
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
# 9. REPORTS
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
# 10. ACTIVITY LOG
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
# ROOT
# ============================================================

@app.get("/")
def root():
    return {
        "message": "CareSync Pro Dashboard API is running"
    }