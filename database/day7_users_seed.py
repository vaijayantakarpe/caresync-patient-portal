print("Connected to caresync.")
import os
import mysql.connector
import bcrypt

# Connect to the caresync database

db_password = os.getenv("DB_PASSWORD")
if not db_password:
    raise RuntimeError(
        "DB_PASSWORD is not configured. Set it in your environment."
    )

conn = mysql.connector.connect(
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", "3306")),
    user=os.getenv("DB_USER", "root"),
    password=db_password,
    database=os.getenv("DB_NAME", "caresync"),
    use_pure=True
)



cur = conn.cursor(dictionary=True)
print("Connected to caresync.")


# Helper: hash a plain password
def make_hash(plain_password: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(plain_password.encode(), salt).decode()


# Pick two real doctors from the database
cur.execute("SELECT doctor_id, full_name FROM doctor LIMIT 2")
doctors = cur.fetchall()

if len(doctors) < 2:
    print("ERROR: Need at least 2 doctors in the database.")
    exit()


# Pick two real patients from the database
cur.execute("SELECT patient_id, full_name FROM patient LIMIT 2")
patients = cur.fetchall()

if len(patients) < 2:
    print("ERROR: Need at least 2 patients in the database.")
    exit()


# Build the list of accounts to insert
accounts = [
    {
        "email": "doctor1@caresync.local",
        "plain_password": "Doctor@1234",
        "role": "doctor",
        "linked_id": doctors[0]["doctor_id"],
        "name": doctors[0]["full_name"]
    },
    {
        "email": "doctor2@caresync.local",
        "plain_password": "Doctor@1234",
        "role": "doctor",
        "linked_id": doctors[1]["doctor_id"],
        "name": doctors[1]["full_name"]
    },
    {
        "email": "patient1@caresync.local",
        "plain_password": "Patient@1234",
        "role": "patient",
        "linked_id": patients[0]["patient_id"],
        "name": patients[0]["full_name"]
    },
    {
        "email": "patient2@caresync.local",
        "plain_password": "Patient@1234",
        "role": "patient",
        "linked_id": patients[1]["patient_id"],
        "name": patients[1]["full_name"]
    },
]


# Insert each account
for acc in accounts:
    hashed = make_hash(acc["plain_password"])

    try:
        cur.execute(
            """
            INSERT INTO users (email, password_hash, role, linked_id)
            VALUES (%s, %s, %s, %s)
            """,
            (acc["email"], hashed, acc["role"], acc["linked_id"])
        )

        conn.commit()

        print(
            f"Inserted: {acc['email']} "
            f"({acc['role']} - {acc['name']})"
        )

    except mysql.connector.IntegrityError:
        print(f"Skipped (already exists): {acc['email']}")


cur.close()
conn.close()

print()
print("Seed complete.")