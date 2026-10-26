# ============================================================
# FILE: triage_ai.py
# ROLE: CareSync AI triage
# PURPOSE: Sends available CareSync patient data to Groq.
# ============================================================

from datetime import date, datetime

from groq import Groq
from dotenv import load_dotenv
import os
import re
from pathlib import Path


# ============================================================
# LOAD EXISTING CARESYNC AI ENVIRONMENT
# ============================================================

AI_DIR = Path(__file__).resolve().parent

# IMPORTANT:
# Explicitly load the existing AI/.env file.
# This works even when Uvicorn is started from auth/.
load_dotenv(AI_DIR / ".env")


GROQ_MODEL = "openai/gpt-oss-20b"


# ============================================================
# AGE CALCULATION
# ============================================================

def _calculate_age(date_of_birth):

    if not date_of_birth:
        return "Not provided"

    if isinstance(
        date_of_birth,
        datetime
    ):

        birth_date = (
            date_of_birth.date()
        )

    elif isinstance(
        date_of_birth,
        date
    ):

        birth_date = date_of_birth

    else:

        try:

            birth_date = datetime.strptime(
                str(date_of_birth)[:10],
                "%Y-%m-%d"
            ).date()

        except (
            TypeError,
            ValueError
        ):

            return "Not provided"

    today = date.today()

    age = (
        today.year
        - birth_date.year
    )

    if (
        today.month,
        today.day
    ) < (
        birth_date.month,
        birth_date.day
    ):

        age -= 1

    return age


# ============================================================
# TRIAGE PROMPT
# ============================================================

def build_prompt(patient):

    name = (
        patient.get("full_name")
        or patient.get("name")
        or "Unknown"
    )

    age = (
        patient.get("age")
        if patient.get("age") is not None
        else _calculate_age(
            patient.get(
                "date_of_birth"
            )
        )
    )

    gender = patient.get(
        "gender",
        "Unknown"
    )

    chief_complaint = (
        patient.get(
            "chief_complaint"
        )
        or patient.get(
            "symptoms"
        )
        or patient.get(
            "complaint"
        )
        or patient.get(
            "description"
        )
        or
        "No symptoms provided in the "
        "CareSync patient record"
    )

    pain_level = patient.get(
        "pain_level",
        "Not provided"
    )

    temperature = patient.get(
        "temperature",
        "Not provided"
    )

    systolic_bp = patient.get(
        "systolic_bp",
        "Not provided"
    )

    diastolic_bp = patient.get(
        "diastolic_bp",
        "Not provided"
    )

    heart_rate = patient.get(
        "heart_rate",
        "Not provided"
    )

    return f"""
You are a hospital triage assistant.

Classify this patient's medical urgency based ONLY on the
information provided.

Patient Name: {name}
Age: {age}
Gender: {gender}

Patient's Chief Complaint / Symptoms:
{chief_complaint}

Pain Level: {pain_level} out of 10

Temperature: {temperature} Celsius

Blood Pressure: {systolic_bp}/{diastolic_bp}

Heart Rate: {heart_rate} bpm

Give the result in this format:

1. Triage Category:
   Immediate / Urgent / Semi-Urgent / Non-Urgent

2. Reason:
   Give one short sentence explaining the classification.

3. Recommended Action:
   Give a short, practical next step.

4. Recommended Doctor/Specialty:
   Suggest the most relevant medical specialty based on
   the patient's symptoms.

Important:
- Do not invent medical measurements.
- If information is missing, say that it is not provided.
- This is a preliminary triage recommendation, not a diagnosis.
- For severe or emergency symptoms, recommend immediate
  emergency medical attention.
"""


# ============================================================
# RUN TRIAGE
# ============================================================

def run_triage(patient):

    api_key = os.getenv(
        "GROQ_API_KEY"
    )

    if not api_key:

        raise RuntimeError(
            "GROQ_API_KEY is missing. "
            "Please check your .env file."
        )

    client = Groq(
        api_key=api_key
    )

    response = (
        client.chat.completions.create(
            model=GROQ_MODEL,

            messages=[
                {
                    "role": "user",
                    "content":
                        build_prompt(
                            patient
                        ),
                }
            ],

            temperature=0.3,

            max_tokens=500,
        )
    )

    return (
        response
        .choices[0]
        .message
        .content
    )


# ============================================================
# APPOINTMENT ROUTING
# ============================================================

def recommend_appointment(
    symptoms,
    doctors
):

    """
    Recommend an existing doctor/specialty
    for appointment routing.

    This is NOT a diagnosis.

    The AI receives:
      1. Patient symptom text.
      2. Real active doctors from CareSync.

    It must return JSON.
    """

    api_key = os.getenv(
        "GROQ_API_KEY"
    )

    if not api_key:

        raise RuntimeError(
            "GROQ_API_KEY is missing. "
            "Please check your .env file."
        )

    import json

    doctor_lines = "\n".join(
        (
            f"- doctor_id={d['doctor_id']}, "
            f"name={d['full_name']}, "
            f"specialisation="
            f"{d['specialisation']}"
        )
        for d in doctors
    )

    prompt = f"""
You are a hospital appointment-routing assistant.

The patient has provided these symptoms/reason
for an appointment:

{symptoms}

Here is the ONLY list of real active doctors
available in the CareSync database:

{doctor_lines}

Choose the most appropriate medical specialty
for appointment routing and, when possible,
one doctor from the supplied list.

Return ONLY valid JSON with exactly these keys:

{{
  "recommended_specialty": "string",
  "recommended_doctor_id": 123,
  "reason": "short routing explanation",
  "disclaimer": "This recommendation is for appointment routing and is not a medical diagnosis."
}}

Rules:

- Do not diagnose the patient.
- Do not claim the patient has a disease.
- Do not invent a doctor.
- recommended_doctor_id must be one of the
  supplied doctor_id values, or null if the
  specialty is clear but a doctor cannot
  confidently be chosen.
- The reason must explain why the specialty
  is relevant to the reported symptoms.
- Do not provide a medical diagnosis.
- Keep the response concise.
"""

    client = Groq(
        api_key=api_key
    )

    response = (
        client
        .chat
        .completions
        .create(
            model=GROQ_MODEL,

            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],

            temperature=0.1,

            max_tokens=300,
        )
    )

    content = (
        response
        .choices[0]
        .message
        .content
        or ""
    ).strip()

    # --------------------------------------------------------
    # Handle fenced JSON
    # --------------------------------------------------------

    if content.startswith("```"):

        content = re.sub(
            r"^```(?:json)?\s*",
            "",
            content
        )

        content = re.sub(
            r"\s*```$",
            "",
            content
        ).strip()

    # --------------------------------------------------------
    # Parse JSON
    # --------------------------------------------------------

    try:

        result = json.loads(
            content
        )

    except json.JSONDecodeError as exc:

        print(
            "AI JSON ERROR:",
            repr(exc)
        )

        print(
            "RAW AI RESPONSE:",
            content
        )

        raise RuntimeError(
            "The AI returned an invalid "
            "appointment recommendation."
        ) from exc

    if not isinstance(
        result,
        dict
    ):

        raise RuntimeError(
            "The AI returned an invalid "
            "appointment recommendation."
        )

    return result