from fastapi import FastAPI, HTTPException, Header

from fastapi.middleware.cors import CORSMiddleware

from pydantic import BaseModel, EmailStr

from fastapi import Query

import mysql.connector

import bcrypt

import jwt

import hashlib

import secrets

import sys

import time

import os

from pathlib import Path

from datetime import datetime, timedelta, timezone, date as date_type, time as time_type

from typing import Optional



# Reuse the existing CareSync AI implementation.

AI_DIR = Path(__file__).resolve().parents[1] / "AI"

if str(AI_DIR) not in sys.path:

    sys.path.insert(0, str(AI_DIR))



from triage_ai import recommend_appointment

from feedback_analyser import analyse_feedback





# ============================================================

# CARESYNC AUTHENTICATION API

# ============================================================



app = FastAPI(title="CareSync Authentication API")





# ============================================================

# CORS

# ============================================================



app.add_middleware(

    CORSMiddleware,

    allow_origins=[

        "http://127.0.0.1:5500",

        "http://localhost:5500",

        "http://127.0.0.1:8000",

        "http://localhost:8000",

    ],

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"],

)





# ============================================================

# DATABASE CONFIGURATION

# ============================================================



DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "caresync"),
    "port": int(os.getenv("DB_PORT", "3306")),
}





# ============================================================

# JWT CONFIGURATION

# ============================================================



JWT_SECRET = os.getenv("JWT_SECRET", "")
if len(JWT_SECRET) < 32:
    raise RuntimeError(
        "JWT_SECRET is not configured. Set JWT_SECRET to a strong random value "
        "of at least 32 characters before starting CareSync."
    )

JWT_ALGORITHM = "HS256"



ACCESS_TOKEN_EXPIRE_MINUTES = 15

REFRESH_TOKEN_EXPIRE_DAYS = 7





# ============================================================

# DATABASE CONNECTION

# ============================================================



def get_db_connection():
    if not DB_CONFIG["password"]:
        raise RuntimeError(
            "DB_PASSWORD is not configured. Set DB_PASSWORD before starting CareSync."
        )
    return mysql.connector.connect(**DB_CONFIG)





# ============================================================

# REQUEST MODELS

# ============================================================



class LoginRequest(BaseModel):

    email: EmailStr

    password: str





class RegisterRequest(BaseModel):

    email: EmailStr

    password: str

    role: str

    linked_id: int





class FeedbackRequest(BaseModel):

    rating: int

    comment: str = ""





class CompleteAppointmentRequest(BaseModel):

    diagnosis: str = ""

    notes: str = ""





# ============================================================

# PASSWORD FUNCTIONS

# ============================================================



def ensure_feedback_table(conn):

    """Ensure the feedback table exists without recreating constraints."""

    cursor = conn.cursor(dictionary=True)

    try:

        cursor.execute(

            "SELECT COUNT(*) AS count FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = 'appointment_feedback'"

        )

        exists = int(cursor.fetchone()["count"] or 0) > 0

        if exists:

            return



        cursor.close()

        cursor = conn.cursor()

        cursor.execute("""

            CREATE TABLE appointment_feedback (

                feedback_id INT NOT NULL AUTO_INCREMENT,

                appointment_id INT NOT NULL,

                patient_id INT NOT NULL,

                doctor_id INT NOT NULL,

                rating TINYINT NOT NULL,

                comment TEXT,

                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

                PRIMARY KEY (feedback_id),

                UNIQUE KEY uq_feedback_appointment (appointment_id),

                CONSTRAINT fk_cs_feedback_appointment

                    FOREIGN KEY (appointment_id) REFERENCES appointment(appointment_id)

                    ON DELETE CASCADE ON UPDATE CASCADE,

                CONSTRAINT fk_cs_feedback_patient

                    FOREIGN KEY (patient_id) REFERENCES patient(patient_id)

                    ON DELETE CASCADE ON UPDATE CASCADE,

                CONSTRAINT fk_cs_feedback_doctor

                    FOREIGN KEY (doctor_id) REFERENCES doctor(doctor_id)

                    ON DELETE CASCADE ON UPDATE CASCADE

            )

        """)

        conn.commit()

    finally:

        cursor.close()





def hash_password(password: str) -> str:

    return bcrypt.hashpw(

        password.encode("utf-8"),

        bcrypt.gensalt()

    ).decode("utf-8")





def verify_password(password: str, password_hash: str) -> bool:
    try:
        if not password_hash:
            return False

        return bcrypt.checkpw(
            password.encode("utf-8"),
            password_hash.encode("utf-8")
        )
    except (ValueError, TypeError):
        return False
    except Exception:
        return False



# JWT FUNCTIONS

# ============================================================



def create_access_token(

    user_id: int,

    email: str,

    role: str,

    linked_id: int

):

    now = datetime.now(timezone.utc)



    expires = now + timedelta(

        minutes=ACCESS_TOKEN_EXPIRE_MINUTES

    )



    payload = {

        "sub": str(user_id),

        "user_id": user_id,

        "email": email,

        "role": role,

        "linked_id": linked_id,

        "type": "access",

        "iat": now,

        "exp": expires,

    }



    return jwt.encode(

        payload,

        JWT_SECRET,

        algorithm=JWT_ALGORITHM

    )





def create_refresh_token():

    return secrets.token_urlsafe(64)





def hash_refresh_token(token: str) -> str:

    return hashlib.sha256(

        token.encode("utf-8")

    ).hexdigest()





# ============================================================

# ROOT

# ============================================================



@app.get("/")

def root():

    return {

        "message": "CareSync Authentication API is running",

        "status": "success"

    }





# ============================================================

# HEALTH CHECK

# ============================================================



@app.get("/health")

def health():

    try:

        conn = get_db_connection()

        conn.close()



        return {

            "status": "healthy",

            "database": "connected"

        }



    except Exception as e:

        return {

            "status": "unhealthy",

            "database": "disconnected",

            "error": str(e)

        }





# ============================================================

# REGISTER

# ============================================================



@app.post("/register")

def register(data: RegisterRequest):



    conn = None

    cursor = None



    try:



        conn = get_db_connection()

        cursor = conn.cursor(dictionary=True)



        # Check whether email already exists

        cursor.execute(

            """

            SELECT user_id

            FROM users

            WHERE email = %s

            """,

            (data.email,)

        )



        existing_user = cursor.fetchone()



        if existing_user:

            raise HTTPException(

                status_code=409,

                detail="Email already registered."

            )



        # Validate role

        allowed_roles = ["doctor", "patient", "billing"]



        if data.role not in allowed_roles:

            raise HTTPException(

                status_code=400,

                detail="Invalid role."

            )



        # Hash password

        password_hash = hash_password(data.password)



        # Insert user

        cursor.execute(

            """

            INSERT INTO users

            (

                email,

                password_hash,

                role,

                linked_id,

                is_active

            )

            VALUES (%s, %s, %s, %s, 1)

            """,

            (

                data.email,

                password_hash,

                data.role,

                data.linked_id

            )

        )



        conn.commit()



        return {

            "success": True,

            "message": "User registered successfully.",

            "user_id": cursor.lastrowid

        }



    except HTTPException:

        raise



    except mysql.connector.Error as e:



        if conn:

            conn.rollback()



        print("REGISTER DATABASE ERROR:", repr(e))



        raise HTTPException(

            status_code=500,

            detail="Database error during registration."

        )



    except Exception as e:



        if conn:

            conn.rollback()



        print("REGISTER ERROR:", repr(e))



        raise HTTPException(

            status_code=500,

            detail="Registration failed."

        )



    finally:



        if cursor:

            cursor.close()



        if conn:

            conn.close()





# ============================================================

# LOGIN

# ============================================================



@app.post("/login")

def login(data: LoginRequest):



    conn = None

    cursor = None



    try:






        conn = get_db_connection()



        cursor = conn.cursor(dictionary=True)



        # ----------------------------------------------------

        # Get user

        # ----------------------------------------------------



        cursor.execute(

            """

            SELECT

                user_id,

                email,

                password_hash,

                role,

                linked_id,

                is_active

            FROM users

            WHERE email = %s

            """,

            (data.email,)

        )



        user = cursor.fetchone()






        if not user:






            raise HTTPException(

                status_code=401,

                detail="Invalid email or password."

            )



        # ----------------------------------------------------

        # Account status

        # ----------------------------------------------------



        if not user["is_active"]:






            raise HTTPException(

                status_code=403,

                detail="User account is inactive."

            )



        # ----------------------------------------------------

        # Password verification

        # ----------------------------------------------------



        stored_hash = user["password_hash"]









        password_match = verify_password(

            data.password,

            stored_hash

        )






        if not password_match:






            raise HTTPException(

                status_code=401,

                detail="Invalid email or password."

            )



        # ----------------------------------------------------

        # Create access token

        # ----------------------------------------------------



        access_token = create_access_token(

            user_id=user["user_id"],

            email=user["email"],

            role=user["role"],

            linked_id=user["linked_id"]

        )



        # ----------------------------------------------------

        # Create refresh token

        # ----------------------------------------------------



        refresh_token = create_refresh_token()



        refresh_token_hash = hash_refresh_token(

            refresh_token

        )



        refresh_expires = datetime.now(timezone.utc) + timedelta(

            days=REFRESH_TOKEN_EXPIRE_DAYS

        )



        # ----------------------------------------------------

        # Save refresh token

        #

        # IMPORTANT:

        # Table uses token_hash, NOT token

        # ----------------------------------------------------



        cursor.execute(

            """

            INSERT INTO refresh_tokens

            (

                user_id,

                token_hash,

                expires_at

            )

            VALUES (%s, %s, %s)

            """,

            (

                user["user_id"],

                refresh_token_hash,

                refresh_expires

            )

        )



        conn.commit()






        return {

            "success": True,

            "message": "Login successful.",



            "access_token": access_token,



            "refresh_token": refresh_token,



            "token_type": "bearer",



            "user": {

                "user_id": user["user_id"],

                "email": user["email"],

                "role": user["role"],

                "linked_id": user["linked_id"],

                "is_active": user["is_active"]

            }

        }



    except HTTPException:

        raise



    except mysql.connector.Error as e:



        if conn:

            conn.rollback()



        print("LOGIN DATABASE ERROR:", repr(e))



        raise HTTPException(
            status_code=500,
            detail="Database error during login. Check the server logs."
        )



    except Exception as e:



        if conn:

            conn.rollback()



        print("LOGIN ERROR:", repr(e))



        raise HTTPException(
            status_code=500,
            detail="Login failed due to a server error."
        )



    finally:



        if cursor:

            cursor.close()



        if conn:

            conn.close()





# ============================================================

# REFRESH TOKEN

# ============================================================



@app.post("/refresh")

def refresh_token(refresh_token: str):



    conn = None

    cursor = None



    try:



        conn = get_db_connection()

        cursor = conn.cursor(dictionary=True)



        token_hash = hash_refresh_token(

            refresh_token

        )



        cursor.execute(

            """

            SELECT

                rt.token_id,

                rt.user_id,

                rt.expires_at,

                u.email,

                u.role,

                u.linked_id,

                u.is_active

            FROM refresh_tokens rt

            INNER JOIN users u

                ON rt.user_id = u.user_id

            WHERE rt.token_hash = %s

            """,

            (token_hash,)

        )



        token_data = cursor.fetchone()



        if not token_data:

            raise HTTPException(

                status_code=401,

                detail="Invalid refresh token."

            )



        # Check expiration

        expires_at = token_data["expires_at"]



        if expires_at.tzinfo is None:

            expires_at = expires_at.replace(

                tzinfo=timezone.utc

            )



        if expires_at < datetime.now(timezone.utc):



            cursor.execute(

                """

                DELETE FROM refresh_tokens

                WHERE token_id = %s

                """,

                (token_data["token_id"],)

            )



            conn.commit()



            raise HTTPException(

                status_code=401,

                detail="Refresh token expired."

            )



        if not token_data["is_active"]:

            raise HTTPException(

                status_code=403,

                detail="User account is inactive."

            )



        new_access_token = create_access_token(

            user_id=token_data["user_id"],

            email=token_data["email"],

            role=token_data["role"],

            linked_id=token_data["linked_id"]

        )



        return {

            "success": True,

            "access_token": new_access_token,

            "token_type": "bearer"

        }



    except HTTPException:

        raise



    except mysql.connector.Error as e:



        print("REFRESH DATABASE ERROR:", repr(e))



        raise HTTPException(

            status_code=500,

            detail="Database error during token refresh."

        )



    except Exception as e:



        print("REFRESH ERROR:", repr(e))



        raise HTTPException(

            status_code=500,

            detail="Refresh failed."

        )



    finally:



        if cursor:

            cursor.close()



        if conn:

            conn.close()





# ============================================================

# LOGOUT

# ============================================================



@app.post("/logout")

def logout(refresh_token: str):



    conn = None

    cursor = None



    try:



        conn = get_db_connection()

        cursor = conn.cursor()



        token_hash = hash_refresh_token(

            refresh_token

        )



        cursor.execute(

            """

            DELETE FROM refresh_tokens

            WHERE token_hash = %s

            """,

            (token_hash,)

        )



        conn.commit()



        return {

            "success": True,

            "message": "Logout successful."

        }



    except mysql.connector.Error as e:



        if conn:

            conn.rollback()



        print("LOGOUT DATABASE ERROR:", repr(e))



        raise HTTPException(

            status_code=500,

            detail="Database error during logout."

        )



    finally:



        if cursor:

            cursor.close()



        if conn:

            conn.close()





# ============================================================

# GET CURRENT USER

# ============================================================



@app.get("/me")

def get_current_user(

    authorization: Optional[str] = Header(None)

):



    if not authorization:

        raise HTTPException(

            status_code=401,

            detail="Authorization header missing."

        )



    if not authorization.lower().startswith("bearer "):



        raise HTTPException(

            status_code=401,

            detail="Invalid authorization header."

        )



    token = authorization.split(" ", 1)[1]



    try:



        payload = jwt.decode(

            token,

            JWT_SECRET,

            algorithms=[JWT_ALGORITHM]

        )



        if payload.get("type") != "access":



            raise HTTPException(

                status_code=401,

                detail="Invalid access token."

            )



        return {

            "success": True,

            "user": {

                "user_id": payload.get("user_id"),

                "email": payload.get("email"),

                "role": payload.get("role"),

                "linked_id": payload.get("linked_id")

            }

        }



    except jwt.ExpiredSignatureError:



        raise HTTPException(

            status_code=401,

            detail="Access token expired."

        )



    except jwt.InvalidTokenError:



        raise HTTPException(

            status_code=401,

            detail="Invalid access token."

        )





# ============================================================

# DOCTOR DASHBOARD

# ============================================================



@app.get("/dashboard/doctor")

def doctor_dashboard(

    authorization: Optional[str] = Header(None)

):



    if not authorization:



        raise HTTPException(

            status_code=401,

            detail="Authorization header missing."

        )



    if not authorization.lower().startswith("bearer "):



        raise HTTPException(

            status_code=401,

            detail="Invalid authorization header."

        )



    token = authorization.split(" ", 1)[1]



    try:



        payload = jwt.decode(

            token,

            JWT_SECRET,

            algorithms=[JWT_ALGORITHM]

        )



        if payload.get("role") != "doctor":



            raise HTTPException(

                status_code=403,

                detail="Doctor access required."

            )



        return {

            "success": True,

            "message": "Doctor dashboard access granted.",

            "doctor": {

                "user_id": payload.get("user_id"),

                "email": payload.get("email"),

                "linked_id": payload.get("linked_id")

            }

        }



    except jwt.ExpiredSignatureError:



        raise HTTPException(

            status_code=401,

            detail="Access token expired."

        )



    except jwt.InvalidTokenError:



        raise HTTPException(

            status_code=401,

            detail="Invalid access token."

        )









# ------------------------------------------------------------

# CANCEL APPOINTMENT

# PUT /api/appointments/{appointment_id}/cancel

# ------------------------------------------------------------



@app.put("/api/appointments/{appointment_id}/cancel")

def cancel_appointment(

    appointment_id: int,

    authorization: Optional[str] = Header(None),

):

    payload = get_token_payload(authorization)

    if payload.get("role") != "patient":

        raise HTTPException(status_code=403, detail="Only patients can cancel appointments.")



    patient_id = payload.get("linked_id")

    conn = cursor = None

    try:

        conn = get_db_connection()

        cursor = conn.cursor(dictionary=True)

        cursor.execute(

            "SELECT status FROM appointment WHERE appointment_id = %s AND patient_id = %s",

            (appointment_id, patient_id),

        )

        appointment = cursor.fetchone()

        if not appointment:

            raise HTTPException(status_code=404, detail="Appointment not found.")

        if appointment["status"] != "Scheduled":

            raise HTTPException(status_code=400, detail="Only scheduled appointments can be cancelled.")



        cursor.execute(

            "UPDATE appointment SET status = 'Cancelled' WHERE appointment_id = %s AND patient_id = %s",

            (appointment_id, patient_id),

        )

        conn.commit()

        return {"success": True, "message": "Appointment cancelled successfully."}

    except HTTPException:

        if conn:

            conn.rollback()

        raise

    except mysql.connector.Error as e:

        if conn:

            conn.rollback()

        raise db_error("Cancelling appointment", e)

    finally:

        if cursor:

            cursor.close()

        if conn:

            conn.close()





# ------------------------------------------------------------

# COMPLETE APPOINTMENT

# PUT /api/appointments/{appointment_id}/complete

# ------------------------------------------------------------



@app.put("/api/appointments/{appointment_id}/complete")

def complete_appointment(

    appointment_id: int,

    request: CompleteAppointmentRequest,

    authorization: Optional[str] = Header(None),

):

    payload = get_token_payload(authorization)

    if payload.get("role") != "doctor":

        raise HTTPException(status_code=403, detail="Doctor access required.")



    doctor_id = payload.get("linked_id")

    conn = cursor = None

    try:

        conn = get_db_connection()

        cursor = conn.cursor(dictionary=True)

        cursor.execute(

            "SELECT status FROM appointment WHERE appointment_id = %s AND doctor_id = %s",

            (appointment_id, doctor_id),

        )

        appointment = cursor.fetchone()

        if not appointment:

            raise HTTPException(status_code=404, detail="Appointment not found.")

        if appointment["status"] != "Scheduled":

            raise HTTPException(status_code=400, detail="Only scheduled appointments can be completed.")



        cursor.execute(

            """

            UPDATE appointment

            SET status = 'Completed', diagnosis = %s, notes = %s

            WHERE appointment_id = %s AND doctor_id = %s

            """,

            (request.diagnosis.strip(), request.notes.strip(), appointment_id, doctor_id),

        )

        conn.commit()

        return {"success": True, "message": "Appointment completed successfully."}

    except HTTPException:

        if conn:

            conn.rollback()

        raise

    except mysql.connector.Error as e:

        if conn:

            conn.rollback()

        raise db_error("Completing appointment", e)

    finally:

        if cursor:

            cursor.close()

        if conn:

            conn.close()





# ------------------------------------------------------------

# PATIENT FEEDBACK

# POST /api/appointments/{appointment_id}/feedback

# ------------------------------------------------------------



@app.post("/api/appointments/{appointment_id}/feedback")

def submit_feedback(

    appointment_id: int,

    request: FeedbackRequest,

    authorization: Optional[str] = Header(None),

):

    payload = get_token_payload(authorization)

    if payload.get("role") != "patient":

        raise HTTPException(status_code=403, detail="Only patients can submit feedback.")



    patient_id = payload.get("linked_id")

    if request.rating < 1 or request.rating > 5:

        raise HTTPException(status_code=400, detail="Rating must be between 1 and 5.")



    conn = cursor = None

    try:

        conn = get_db_connection()

        ensure_feedback_table(conn)

        cursor = conn.cursor(dictionary=True)



        cursor.execute(

            """

            SELECT doctor_id, status

            FROM appointment

            WHERE appointment_id = %s AND patient_id = %s

            """,

            (appointment_id, patient_id),

        )

        appointment = cursor.fetchone()

        if not appointment:

            raise HTTPException(status_code=404, detail="Appointment not found.")

        if appointment["status"] != "Completed":

            raise HTTPException(

                status_code=400,

                detail="Feedback can only be submitted for completed appointments.",

            )



        cursor.execute(

            "SELECT feedback_id FROM appointment_feedback WHERE appointment_id = %s",

            (appointment_id,),

        )

        if cursor.fetchone():

            raise HTTPException(status_code=409, detail="Feedback has already been submitted for this appointment.")



        cursor.execute(

            """

            INSERT INTO appointment_feedback

                (appointment_id, patient_id, doctor_id, rating, comment)

            VALUES (%s, %s, %s, %s, %s)

            """,

            (appointment_id, patient_id, appointment["doctor_id"], request.rating, request.comment.strip()),

        )

        new_feedback_id = cursor.lastrowid

        conn.commit()

        return {

            "success": True,

            "feedback_id": new_feedback_id,

            "message": "Feedback submitted successfully.",

        }

    except HTTPException:

        if conn:

            conn.rollback()

        raise

    except mysql.connector.Error as e:

        if conn:

            conn.rollback()

        print("FEEDBACK DATABASE ERROR:", repr(e))

        raise db_error("Submitting feedback", e)

    finally:

        if cursor:

            cursor.close()

        if conn:

            conn.close()





# ------------------------------------------------------------

# DOCTOR FEEDBACK

# GET /api/doctor/feedback

# ------------------------------------------------------------



@app.get("/api/doctor/feedback")

def doctor_feedback(authorization: Optional[str] = Header(None)):

    payload = get_token_payload(authorization)

    if payload.get("role") != "doctor":

        raise HTTPException(status_code=403, detail="Doctor access required.")



    doctor_id = payload.get("linked_id")

    conn = cursor = None

    try:

        conn = get_db_connection()

        ensure_feedback_table(conn)

        cursor = conn.cursor(dictionary=True)

        cursor.execute(

            """

            SELECT f.feedback_id, f.appointment_id, f.rating, f.comment,

                   DATE_FORMAT(f.created_at, '%Y-%m-%d %H:%i') AS created_at,

                   p.full_name AS patient_name,

                   DATE_FORMAT(a.appointment_date, '%Y-%m-%d') AS appointment_date,

                   TIME_FORMAT(a.appointment_time, '%H:%i:%s') AS appointment_time

            FROM appointment_feedback f

            JOIN patient p ON p.patient_id = f.patient_id

            JOIN appointment a ON a.appointment_id = f.appointment_id

            WHERE f.doctor_id = %s

            ORDER BY f.created_at DESC

            """,

            (doctor_id,),

        )

        return {"success": True, "feedback": cursor.fetchall()}

    except mysql.connector.Error as e:

        print("DOCTOR FEEDBACK DATABASE ERROR:", repr(e))

        raise db_error("Loading feedback", e)

    finally:

        if cursor:

            cursor.close()

        if conn:

            conn.close()



# ------------------------------------------------------------

# DOCTOR FEEDBACK ANALYSIS (AI)

# GET /api/doctor/feedback/analysis

#

# Ratings are summarised in Python; the written comments are

# analysed by Groq (see AI/feedback_analyser.py). If the AI call

# fails, the statistics are still returned.

#

# ?refresh=true  forces a new AI run instead of using the cache.

# ------------------------------------------------------------



FEEDBACK_ANALYSIS_MAX_ROWS = 500

FEEDBACK_ANALYSIS_COOLDOWN_SECONDS = 10

FEEDBACK_ANALYSIS_CACHE_LIMIT = 200



# {(doctor_id, feedback_count, newest_feedback_id): analysis}

# New feedback changes the key, so a stale result is never served.

_feedback_analysis_cache = {}



# {doctor_id: monotonic time of the last AI run}

_feedback_analysis_last_run = {}





@app.get("/api/doctor/feedback/analysis")

def doctor_feedback_analysis(

    refresh: bool = Query(False),

    authorization: Optional[str] = Header(None),

):

    payload = get_token_payload(authorization)

    if payload.get("role") != "doctor":

        raise HTTPException(status_code=403, detail="Doctor access required.")



    doctor_id = payload.get("linked_id")



    # Read the rows, then release the DB connection BEFORE the

    # (slow) AI call so we never hold it while waiting on Groq.

    conn = cursor = None

    try:

        conn = get_db_connection()

        ensure_feedback_table(conn)

        cursor = conn.cursor(dictionary=True)

        cursor.execute(

            """

            SELECT f.feedback_id, f.rating, f.comment,

                   DATE_FORMAT(f.created_at, '%Y-%m-%d %H:%i') AS created_at,

                   p.full_name AS patient_name

            FROM appointment_feedback f

            JOIN patient p ON p.patient_id = f.patient_id

            WHERE f.doctor_id = %s

            ORDER BY f.created_at DESC, f.feedback_id DESC

            LIMIT %s

            """,

            (doctor_id, FEEDBACK_ANALYSIS_MAX_ROWS),

        )

        rows = cursor.fetchall()

    except mysql.connector.Error as e:

        print("DOCTOR FEEDBACK ANALYSIS DATABASE ERROR:", repr(e))

        raise db_error("Analysing feedback", e)

    finally:

        if cursor:

            cursor.close()

        if conn:

            conn.close()



    cache_key = (

        doctor_id,

        len(rows),

        max((row["feedback_id"] for row in rows), default=0),

    )



    if not refresh and cache_key in _feedback_analysis_cache:

        return {

            "success": True,

            "cached": True,

            "row_limit": FEEDBACK_ANALYSIS_MAX_ROWS,

            **_feedback_analysis_cache[cache_key],

        }



    # Guard the shared Groq key against double-clicks / hammering.

    now = time.monotonic()

    last_run = _feedback_analysis_last_run.get(doctor_id)

    if last_run is not None and now - last_run < FEEDBACK_ANALYSIS_COOLDOWN_SECONDS:

        raise HTTPException(

            status_code=429,

            detail="Please wait a few seconds before running the analysis again.",

        )

    _feedback_analysis_last_run[doctor_id] = now



    analysis = analyse_feedback(rows)



    # Never cache an AI failure, so the next click can try again.

    if analysis["ai"]["status"] != "unavailable":

        if len(_feedback_analysis_cache) >= FEEDBACK_ANALYSIS_CACHE_LIMIT:

            _feedback_analysis_cache.clear()

        _feedback_analysis_cache[cache_key] = analysis



    return {

        "success": True,

        "cached": False,

        "row_limit": FEEDBACK_ANALYSIS_MAX_ROWS,

        **analysis,

    }





# ============================================================

# RUN INFORMATION

# ============================================================



@app.get("/api")

def api_info():



    return {

        "application": "CareSync",

        "service": "Authentication API",

        "version": "1.0",

        "status": "running"

    }





# ============================================================

# APPOINTMENT BOOKING

# ------------------------------------------------------------

# Uses ONLY the existing tables in the `caresync` database:

#

#   doctor        (doctor_id, full_name, specialisation, is_active)

#   appointment(s) in the live database. The API detects the

#   existing table name at runtime and never creates a new table.

#

# Expected columns:

#   id/appointment_id, patient_id, doctor_id, appointment_date,

#   appointment_time, reason, status

# ============================================================



# Default working schedule (no working-hours table exists).

DEFAULT_SLOTS = [

    "09:00", "09:15", "09:30", "09:45",

    "10:00", "10:15", "10:30", "10:45",

    "11:00", "11:15", "11:30", "11:45",

    "12:00", "12:15", "12:30", "12:45",

    "13:00", "13:15", "13:30", "13:45",

    "14:00", "14:15", "14:30", "14:45",

    "15:00", "15:15", "15:30", "15:45",

    "16:00", "16:15", "16:30", "16:45",

]



# A cancelled appointment frees its slot again.

ACTIVE_STATUSES_SQL = "status = 'Scheduled'"





class BookAppointmentRequest(BaseModel):

    doctor_id: int

    appointment_date: str

    appointment_time: str

    patient_id: Optional[int] = None

    symptoms: Optional[str] = None

    reason: Optional[str] = None





def get_token_payload(authorization: Optional[str]) -> dict:

    if not authorization or not authorization.lower().startswith("bearer "):

        raise HTTPException(status_code=401, detail="Authorization header missing or invalid.")



    token = authorization.split(" ", 1)[1]



    try:

        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])

    except jwt.ExpiredSignatureError:

        raise HTTPException(status_code=401, detail="Access token expired.")

    except jwt.InvalidTokenError:

        raise HTTPException(status_code=401, detail="Invalid access token.")



    if payload.get("type") != "access":

        raise HTTPException(status_code=401, detail="Invalid access token.")



    return payload





def parse_date(value: str) -> date_type:

    try:

        return date_type.fromisoformat(str(value).strip())

    except ValueError:

        raise HTTPException(status_code=400, detail="appointment_date must use the format YYYY-MM-DD.")





def normalize_time(value) -> Optional[str]:

    """Convert MySQL TIME (timedelta), 'HH:MM' or 'HH:MM:SS' to 'HH:MM'."""

    if value is None:

        return None

    if isinstance(value, timedelta):

        total = int(value.total_seconds())

        return f"{total // 3600:02d}:{(total % 3600) // 60:02d}"

    if isinstance(value, time_type):

        return value.strftime("%H:%M")

    parts = str(value).strip().split(":")

    if len(parts) < 2 or not parts[0].isdigit() or not parts[1].isdigit():

        return None

    return f"{int(parts[0]):02d}:{int(parts[1]):02d}"





def slot_is_in_past(day: date_type, slot: str) -> bool:

    now = datetime.now()

    if day < now.date():

        return True

    if day == now.date():

        return slot <= now.strftime("%H:%M")

    return False





def db_error(label: str, e: Exception):

    print(f"{label} DATABASE ERROR:", repr(e))

    return HTTPException(status_code=500, detail=f"{label} failed due to a database error.")





def doctor_exists(cursor, doctor_id: int, lock: bool = False):

    cursor.execute(

        "SELECT doctor_id, full_name, specialisation FROM doctor "

        "WHERE doctor_id = %s AND is_active = 1" + (" FOR UPDATE" if lock else ""),

        (doctor_id,),

    )

    return cursor.fetchone()





def get_appointment_table(cursor) -> str:

    """

    CareSync uses the existing singular `appointment` table.

    Do not dynamically detect or create another table.

    """

    return "appointment"





def get_appointment_id_column(cursor, table_name: str) -> str:

    """CareSync appointment primary key is appointment_id."""

    return "appointment_id"



def booked_times(cursor, doctor_id: int, day: date_type) -> set:

    table_name = get_appointment_table(cursor)

    cursor.execute(

        f"SELECT appointment_time FROM `{table_name}` "

        f"WHERE doctor_id = %s AND appointment_date = %s AND {ACTIVE_STATUSES_SQL}",

        (doctor_id, day),

    )

    return {normalize_time(row["appointment_time"]) for row in cursor.fetchall()}





# ------------------------------------------------------------

# AI SYMPTOM ANALYSIS / APPOINTMENT ROUTING

# POST /api/appointments/analyze-symptoms

# ------------------------------------------------------------



class AnalyzeSymptomsRequest(BaseModel):

    symptoms: str





@app.post("/api/appointments/analyze-symptoms")

def analyze_appointment_symptoms(

    data: AnalyzeSymptomsRequest,

    authorization: Optional[str] = Header(None),

):

    payload = get_token_payload(authorization)



    if payload.get("role") != "patient":

        raise HTTPException(

            status_code=403,

            detail="Only patients can use appointment symptom analysis.",

        )



    symptoms = str(data.symptoms or "").strip()

    if not symptoms:

        raise HTTPException(

            status_code=400,

            detail="Please describe your symptoms before analysis.",

        )



    conn = cursor = None

    try:

        conn = get_db_connection()

        cursor = conn.cursor(dictionary=True)



        cursor.execute(

            "SELECT doctor_id, full_name, specialisation "

            "FROM doctor WHERE is_active = 1 ORDER BY full_name"

        )

        doctors = cursor.fetchall()



        if not doctors:

            raise HTTPException(

                status_code=404,

                detail="No suitable doctor was found. Please contact the hospital.",

            )



        result = recommend_appointment(symptoms, doctors)



        specialty = str(result.get("recommended_specialty") or "").strip()

        doctor_id = result.get("recommended_doctor_id")



        # Never trust an AI-generated doctor id unless it exists in

        # the current database result set.

        doctor = None

        if doctor_id is not None:

            try:

                doctor_id = int(doctor_id)

            except (TypeError, ValueError):

                doctor_id = None



        if doctor_id is not None:

            doctor = next(

                (d for d in doctors if int(d["doctor_id"]) == doctor_id),

                None,

            )



        # If AI selected a specialty but no valid doctor id, select

        # a real active doctor from that specialty.

        if doctor is None and specialty:

            specialty_lower = specialty.casefold()

            doctor = next(

                (

                    d for d in doctors

                    if str(d.get("specialisation") or "").strip().casefold()

                    == specialty_lower

                ),

                None,

            )



            if doctor is None:

                doctor = next(

                    (

                        d for d in doctors

                        if specialty_lower in str(

                            d.get("specialisation") or ""

                        ).casefold()

                        or str(

                            d.get("specialisation") or ""

                        ).casefold() in specialty_lower

                    ),

                    None,

                )



        if doctor is None:

            raise HTTPException(

                status_code=404,

                detail="No suitable doctor was found. Please contact the hospital.",

            )



        return {

            "success": True,

            "recommended_specialty": doctor["specialisation"],

            "recommended_doctor_id": doctor["doctor_id"],

            "recommended_doctor_name": doctor["full_name"],

            "doctor": {

                "doctor_id": doctor["doctor_id"],

                "full_name": doctor["full_name"],

                "specialisation": doctor["specialisation"],

            },

            "reason": (

                result.get("reason")

                or (

                    "Your symptoms appear most relevant to the "

                    f"{doctor['specialisation']} specialty."

                )

            ),

            "disclaimer": (

                "This recommendation is for appointment routing "

                "and is not a medical diagnosis."

            ),

        }



    except HTTPException:

        raise

    except Exception as e:

        print("SYMPTOM ANALYSIS ERROR:", repr(e))

        raise HTTPException(

            status_code=500,

            detail="Unable to analyze symptoms right now. Please try again.",

        )

    finally:

        if cursor:

            cursor.close()

        if conn:

            conn.close()





# ------------------------------------------------------------

# DOCTORS (patient booking dropdown)

# ------------------------------------------------------------



@app.get("/api/doctors")

def list_doctors(authorization: Optional[str] = Header(None)):

    get_token_payload(authorization)



    conn = cursor = None

    try:

        conn = get_db_connection()

        cursor = conn.cursor(dictionary=True)

        cursor.execute(

            "SELECT doctor_id, full_name, specialisation FROM doctor "

            "WHERE is_active = 1 ORDER BY full_name"

        )

        return {"success": True, "doctors": cursor.fetchall()}

    except mysql.connector.Error as e:

        raise db_error("Loading doctors", e)

    finally:

        if cursor:

            cursor.close()

        if conn:

            conn.close()





# ------------------------------------------------------------

# AVAILABILITY

# GET /api/doctors/{doctor_id}/availability?appointment_date=YYYY-MM-DD

# ------------------------------------------------------------



@app.get("/api/doctors/{doctor_id}/availability")

def doctor_availability(

    doctor_id: int,

    appointment_date: str = Query(...),

    authorization: Optional[str] = Header(None),

):

    get_token_payload(authorization)

    day = parse_date(appointment_date)



    conn = cursor = None

    try:

        conn = get_db_connection()

        cursor = conn.cursor(dictionary=True)



        doctor = doctor_exists(cursor, doctor_id)

        if not doctor:

            raise HTTPException(status_code=404, detail="Doctor not found.")



        booked = booked_times(cursor, doctor_id, day)



        available = [

            slot for slot in DEFAULT_SLOTS

            if slot not in booked and not slot_is_in_past(day, slot)

        ]



        return {

            "success": True,

            "doctor_id": doctor_id,

            "doctor_name": doctor["full_name"],

            "appointment_date": day.isoformat(),

            "available_slots": available,

            "slots": available,

            "booked_slots": sorted(t for t in booked if t),

        }



    except HTTPException:

        raise

    except mysql.connector.Error as e:

        raise db_error("Loading availability", e)

    finally:

        if cursor:

            cursor.close()

        if conn:

            conn.close()





# ------------------------------------------------------------

# BOOK

# POST /api/appointments/book

# ------------------------------------------------------------



@app.post("/api/appointments/book")

def book_appointment(

    data: BookAppointmentRequest,

    authorization: Optional[str] = Header(None),

):

    payload = get_token_payload(authorization)



    if payload.get("role") != "patient":

        raise HTTPException(status_code=403, detail="Only patients can book appointments.")



    patient_id = payload.get("linked_id")

    if patient_id is None:

        raise HTTPException(status_code=400, detail="This account is not linked to a patient record.")



    if data.patient_id is not None and int(data.patient_id) != int(patient_id):

        raise HTTPException(status_code=403, detail="patient_id does not match the logged-in patient.")



    day = parse_date(data.appointment_date)

    slot = normalize_time(data.appointment_time)



    if slot not in DEFAULT_SLOTS:

        raise HTTPException(status_code=400, detail="Selected time is not a valid appointment slot.")



    if slot_is_in_past(day, slot):

        raise HTTPException(status_code=400, detail="Appointment must be in the future.")



    reason = (data.symptoms or data.reason or "").strip()

    if not reason:

        raise HTTPException(status_code=400, detail="Please enter your symptoms or reason for the visit.")



    conn = cursor = None

    try:

        conn = get_db_connection()

        cursor = conn.cursor(dictionary=True)



        # Locking the doctor row serialises bookings for this doctor,

        # so two patients cannot take the same slot at the same moment.

        doctor = doctor_exists(cursor, data.doctor_id, lock=True)

        if not doctor:

            raise HTTPException(status_code=404, detail="Doctor not found.")



        if slot in booked_times(cursor, data.doctor_id, day):

            conn.rollback()

            raise HTTPException(

                status_code=409,

                detail="This time slot is already booked. Please choose another time.",

            )



        appointment_table = get_appointment_table(cursor)

        cursor.execute(

            f"""

            INSERT INTO `{appointment_table}`

                (patient_id, doctor_id, appointment_date, appointment_time, reason, status)

            VALUES (%s, %s, %s, %s, %s, 'Scheduled')

            """,

            (patient_id, data.doctor_id, day, slot + ":00", reason),

        )

        new_id = cursor.lastrowid

        conn.commit()



        return {

            "success": True,

            "message": "Message Received",

            "appointment": {

                "id": new_id,

                "appointment_id": new_id,

                "patient_id": patient_id,

                "doctor_id": data.doctor_id,

                "doctor_name": doctor["full_name"],

                "specialisation": doctor["specialisation"],

                "appointment_date": day.isoformat(),

                "appointment_time": slot,

                "reason": reason,

                "status": "Scheduled",

            },

        }



    except HTTPException:

        raise

    except mysql.connector.IntegrityError as e:

        if conn:

            conn.rollback()

        print("BOOKING INTEGRITY ERROR:", repr(e))

        raise HTTPException(

            status_code=400,

            detail="Appointment could not be saved. Check that your patient record and the doctor exist.",

        )

    except mysql.connector.Error as e:

        if conn:

            conn.rollback()

        raise db_error("Booking appointment", e)

    finally:

        if cursor:

            cursor.close()

        if conn:

            conn.close()





# ------------------------------------------------------------

# MY APPOINTMENTS

# GET /api/appointments/my

# ------------------------------------------------------------



@app.get("/api/appointments/my")

def my_appointments(authorization: Optional[str] = Header(None)):

    payload = get_token_payload(authorization)

    patient_id = payload.get("linked_id")



    conn = cursor = None

    try:

        conn = get_db_connection()

        cursor = conn.cursor(dictionary=True)

        appointment_table = get_appointment_table(cursor)

        appointment_id_column = get_appointment_id_column(cursor, appointment_table)

        ensure_feedback_table(conn)

        cursor.execute(

            f"""

            SELECT a.`{appointment_id_column}` AS appointment_id,

                   a.doctor_id, a.appointment_date, a.appointment_time,

                   a.reason, a.status, d.full_name AS doctor_name,

                   d.specialisation, f.feedback_id,

                   f.rating AS feedback_rating,

                   f.comment AS feedback_comment

            FROM `{appointment_table}` a

            LEFT JOIN doctor d ON d.doctor_id = a.doctor_id

            LEFT JOIN appointment_feedback f ON f.appointment_id = a.`{appointment_id_column}`

            WHERE a.patient_id = %s

            ORDER BY a.appointment_date DESC, a.appointment_time DESC

            """,

            (patient_id,),

        )

        rows = cursor.fetchall()



        appointments = [

            {

                "id": r["appointment_id"],

                "appointment_id": r["appointment_id"],

                "doctor_id": r["doctor_id"],

                "doctor_name": r["doctor_name"],

                "specialisation": r["specialisation"],

                "appointment_date": r["appointment_date"].isoformat(),

                "appointment_time": normalize_time(r["appointment_time"]),

                "reason": r["reason"],

                "status": r["status"],

                "feedback_id": r.get("feedback_id"),

                "feedback_rating": r.get("feedback_rating"),

                "feedback_comment": r.get("feedback_comment"),

            }

            for r in rows

        ]

        return {"success": True, "appointments": appointments}



    except mysql.connector.Error as e:

        raise db_error("Loading appointments", e)

    finally:

        if cursor:

            cursor.close()

        if conn:

            conn.close()