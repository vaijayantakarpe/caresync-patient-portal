# generate_data.py
# CareSync Pro Sample Data Generator
#
# This script populates the caresync_pro database with realistic test data
# across ALL 8 tables: doctor, patient, appointment, billing, prescription,
# notification, report, and activity_log.
#
# Run this ONCE after creating your database and all 8 tables.
# Running it twice will cause errors because some unique values will repeat.
#
# Required libraries. Install them before running this script:
#   pip install mysql-connector-python
#   pip install Faker

import mysql.connector       # connects Python to MySQL
import random                # for generating random numbers and choices
from faker import Faker      # generates realistic fake names, addresses, etc.
from datetime import date, timedelta, datetime
import decimal

# Create a Faker instance set to India so names look realistic.
fake = Faker('en_IN')

# ─── DATABASE CONNECTION ────────────────────────────────────────────────────
# Change password if you used something different during MySQL setup.
connection = mysql.connector.connect(
    host='localhost',          # MySQL is running on this same computer
    port=3306,                 # Default MySQL port
    user='root',                # The administrator user
database='caresync_pro'     # The database we created
)
cursor = connection.cursor()

print('Connected to MySQL successfully.')

# ─── CONSTANTS ──────────────────────────────────────────────────────────────
NUM_DOCTORS        = 40
NUM_PATIENTS        = 500
NUM_APPOINTMENTS    = 3000
NUM_BILLS           = 2500
NUM_NOTIFICATIONS   = 1200
NUM_ACTIVITY_LOGS   = 5000
BILL_REJECT_LOW     = 0.08   # 8 percent minimum rejection rate
BILL_REJECT_HIGH    = 0.12   # 12 percent maximum rejection rate

SPECIALISATIONS = [
    'Cardiology', 'General Medicine', 'Orthopaedics', 'Gynaecology',
    'Paediatrics', 'Neurology', 'Dermatology', 'Ophthalmology',
    'ENT', 'Psychiatry', 'Oncology', 'Urology', 'Endocrinology'
]

BLOOD_GROUPS = ['A+', 'A-', 'B+', 'B-', 'O+', 'O-', 'AB+', 'AB-']

DIAGNOSES = [
    'Hypertension', 'Type 2 Diabetes', 'Upper Respiratory Infection',
    'Migraine', 'Lumbar Spondylosis', 'Anxiety Disorder', 'Anaemia',
    'Hypothyroidism', 'Gastritis', 'Urinary Tract Infection',
    'Dengue Fever', 'Viral Fever', 'Asthma', 'Arthritis', 'Obesity',
    'Iron Deficiency', 'Vitamin D Deficiency', 'Sinusitis', 'Eczema'
]

REJECTION_REASONS = [
    'Insurance claim limit exceeded for this policy year.',
    'Procedure not covered under current insurance plan.',
    'Pre-authorisation was not obtained before treatment.',
    'Patient not eligible under submitted insurance policy number.',
    'Duplicate claim submitted for the same service date.',
    'Medical documents submitted are incomplete.',
    'Claim submitted after the deadline specified by insurer.'
]

MEDICINES = [
    ('Paracetamol 500mg', '1 tablet', 'Twice a day', 5),
    ('Amoxicillin 250mg', '1 capsule', 'Three times a day', 7),
    ('Metformin 500mg', '1 tablet', 'Twice a day', 30),
    ('Amlodipine 5mg', '1 tablet', 'Once a day', 30),
    ('Cetirizine 10mg', '1 tablet', 'Once a day', 5),
    ('Omeprazole 20mg', '1 capsule', 'Once a day before food', 14),
    ('Azithromycin 500mg', '1 tablet', 'Once a day', 3),
    ('Ibuprofen 400mg', '1 tablet', 'As needed for pain', 5),
    ('Vitamin D3 60000IU', '1 sachet', 'Once a week', 8),
    ('Levothyroxine 50mcg', '1 tablet', 'Once a day, empty stomach', 30),
]

NOTIFICATION_TEMPLATES = [
    ('Appointment Reminder', 'Your appointment is scheduled soon. Please arrive 15 minutes early.'),
    ('Bill Generated', 'A new bill has been generated for your recent visit.'),
    ('Payment Received', 'We have received your payment. Thank you.'),
    ('Report Ready', 'Your lab report is now ready for download.'),
    ('Prescription Updated', 'A new prescription has been added to your record.'),
    ('Appointment Cancelled', 'Your appointment has been cancelled. Please reschedule.'),
    ('New Patient Assigned', 'A new patient has been assigned to your schedule.'),
    ('Claim Rejected', 'A billing claim was rejected. Please review the reason.'),
]

REPORT_TYPES = [
    'Blood Test', 'X-Ray', 'MRI Scan', 'ECG', 'Urine Test',
    'CT Scan', 'Ultrasound', 'Liver Function Test', 'Thyroid Panel'
]

LOG_ACTIONS = [
    'VIEW_RECORD', 'UPDATE_RECORD', 'CREATE_APPOINTMENT', 'CANCEL_APPOINTMENT',
    'UPDATE_BILL_STATUS', 'LOGIN', 'LOGOUT', 'VIEW_PRESCRIPTION',
    'DOWNLOAD_REPORT', 'SOFT_DELETE_PATIENT'
]

# ─── STEP 1: INSERT DOCTORS ─────────────────────────────────────────────────
print(f'Inserting {NUM_DOCTORS} doctors...')

doctor_ids = []  # We store the IDs so we can use them later.

for i in range(NUM_DOCTORS):
    name   = 'Dr. ' + fake.name()
    spec   = random.choice(SPECIALISATIONS)
    phone  = '9' + str(random.randint(100000000, 999999999))  # 10-digit Indian number
    email  = f'doctor{i+1}@caresync.in'  # Unique email using the loop counter
    lic    = f'MCI-{2000 + i:04d}'       # Unique licence number

    cursor.execute(
        '''
        INSERT INTO doctor (full_name, specialisation, phone, email, licence_number)
        VALUES (%s, %s, %s, %s, %s)
        ''',
        (name, spec, phone, email, lic)
    )
    doctor_ids.append(cursor.lastrowid)  # lastrowid gives us the auto-generated ID

connection.commit()
print(f'  Done. Inserted {len(doctor_ids)} doctors.')

# ─── STEP 2: INSERT PATIENTS ────────────────────────────────────────────────
print(f'Inserting {NUM_PATIENTS} patients...')

patient_ids = []

for i in range(NUM_PATIENTS):
    name      = fake.name()
    dob       = fake.date_of_birth(minimum_age=5, maximum_age=85)
    gender    = random.choice(['Male', 'Female'])
    phone     = '9' + str(random.randint(100000000, 999999999))
    email     = f'patient{i+1}@example.com'
    address   = fake.address().replace('\n', ', ')
    blood     = random.choice(BLOOD_GROUPS)
    ec_name   = fake.name()
    ec_phone  = '9' + str(random.randint(100000000, 999999999))

    cursor.execute(
        '''
        INSERT INTO patient
            (full_name, date_of_birth, gender, phone, email, address,
             blood_group, emergency_contact_name, emergency_contact_phone)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''',
        (name, dob, gender, phone, email, address, blood, ec_name, ec_phone)
    )
    patient_ids.append(cursor.lastrowid)

connection.commit()
print(f'  Done. Inserted {len(patient_ids)} patients.')

# ─── STEP 3: INSERT APPOINTMENTS ────────────────────────────────────────────
print(f'Inserting {NUM_APPOINTMENTS} appointments...')

appointment_ids = []

start_date = date.today() - timedelta(days=730)
end_date   = date.today()

hour_options   = list(range(9, 17))
minute_options = [0, 15, 30, 45]

for _ in range(NUM_APPOINTMENTS):
    p_id    = random.choice(patient_ids)
    d_id    = random.choice(doctor_ids)
    appt_dt = start_date + timedelta(days=random.randint(0, 730))
    appt_tm = f'{random.choice(hour_options):02d}:{random.choice(minute_options):02d}:00'
    reason  = 'Patient complaints of ' + random.choice(DIAGNOSES).lower()
    diag    = random.choice(DIAGNOSES)

    status  = random.choices(
        ['Completed', 'Scheduled', 'Cancelled'],
        weights=[80, 10, 10]
    )[0]

    cursor.execute(
        '''
        INSERT INTO appointment
            (patient_id, doctor_id, appointment_date, appointment_time,
             reason, diagnosis, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''',
        (p_id, d_id, appt_dt, appt_tm, reason, diag, status)
    )
    appointment_ids.append(cursor.lastrowid)

connection.commit()
print(f'  Done. Inserted {len(appointment_ids)} appointments.')

# Fetch the completed appointments once — we reuse this list for billing,
# prescriptions, and reports.
cursor.execute(
    'SELECT appointment_id, patient_id, doctor_id, appointment_date '
    'FROM appointment WHERE status = %s',
    ('Completed',)
)
completed_appointments = cursor.fetchall()  # list of (appt_id, patient_id, doctor_id, appt_date)

# ─── STEP 4: INSERT BILLS ───────────────────────────────────────────────────
print(f'Inserting bills for completed appointments...')

if len(completed_appointments) < NUM_BILLS:
    print(f'  Note: Only {len(completed_appointments)} completed appointments available.')
    print(f'  Will create one bill per completed appointment instead of {NUM_BILLS}.')
    bills_to_create = completed_appointments
else:
    bills_to_create = random.sample(completed_appointments, NUM_BILLS)

reject_rate = random.uniform(BILL_REJECT_LOW, BILL_REJECT_HIGH)
print(f'  Bill rejection rate for this run: {reject_rate*100:.1f}%')

bills_inserted = 0

for (appt_id, p_id, d_id, appt_date) in bills_to_create:
    total = round(random.uniform(300, 3000), 2)
    rand_val = random.random()

    if rand_val < reject_rate:
        status         = 'Rejected'
        amount_paid    = 0.00
        discount       = 0.00
        reject_reason  = random.choice(REJECTION_REASONS)
    elif rand_val < reject_rate + 0.10:
        status         = 'Partially Paid'
        paid_pct       = random.uniform(0.30, 0.70)
        amount_paid    = round(total * paid_pct, 2)
        discount       = 0.00
        reject_reason  = None
    elif rand_val < reject_rate + 0.15:
        status         = 'Pending'
        amount_paid    = 0.00
        discount       = 0.00
        reject_reason  = None
    else:
        status         = 'Paid'
        discount       = round(total * random.uniform(0, 0.05), 2)
        amount_paid    = round(total - discount, 2)
        reject_reason  = None

    bill_date  = appt_date + timedelta(days=random.randint(0, 2))
    due_date   = bill_date + timedelta(days=30)

    cursor.execute(
        '''
        INSERT INTO billing
            (appointment_id, patient_id, total_amount, amount_paid, discount,
             status, rejection_reason, bill_date, due_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''',
        (appt_id, p_id, total, amount_paid, discount,
         status, reject_reason, bill_date, due_date)
    )
    bills_inserted += 1

connection.commit()
print(f'  Done. Inserted {bills_inserted} bills.')

# ─── STEP 5: INSERT PRESCRIPTIONS ───────────────────────────────────────────
# Most completed appointments get 1 to 3 prescribed medicines.
print('Inserting prescriptions for completed appointments...')

prescriptions_inserted = 0

for (appt_id, p_id, d_id, appt_date) in completed_appointments:
    # Not every completed appointment results in a prescription (e.g. follow-ups
    # where nothing new was prescribed) — skip about 20% of the time.
    if random.random() < 0.20:
        continue

    num_medicines = random.randint(1, 3)
    chosen_medicines = random.sample(MEDICINES, num_medicines)

    for (med_name, dosage, frequency, duration) in chosen_medicines:
        instructions = random.choice([
            'Take after food.', 'Take before food.',
            'Avoid alcohol while on this medication.',
            'Complete the full course even if symptoms improve.',
            None
        ])
        cursor.execute(
            '''
            INSERT INTO prescription
                (appointment_id, patient_id, doctor_id, medicine_name,
                 dosage, frequency, duration_days, instructions)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ''',
            (appt_id, p_id, d_id, med_name, dosage, frequency, duration, instructions)
        )
        prescriptions_inserted += 1

connection.commit()
print(f'  Done. Inserted {prescriptions_inserted} prescriptions.')

# ─── STEP 6: INSERT REPORTS ─────────────────────────────────────────────────
# About 40% of completed appointments generate a diagnostic report.
print('Inserting reports for completed appointments...')

reports_inserted = 0

for (appt_id, p_id, d_id, appt_date) in completed_appointments:
    if random.random() > 0.40:
        continue

    report_type = random.choice(REPORT_TYPES)
    file_path   = f'/reports/{p_id}/{appt_id}_{report_type.replace(" ", "_").lower()}.pdf'

    cursor.execute(
        '''
        INSERT INTO report
            (patient_id, appointment_id, report_type, file_path, generated_by)
        VALUES (%s, %s, %s, %s, %s)
        ''',
        (p_id, appt_id, report_type, file_path, d_id)
    )
    reports_inserted += 1

connection.commit()
print(f'  Done. Inserted {reports_inserted} reports.')

# ─── STEP 7: INSERT NOTIFICATIONS ───────────────────────────────────────────
print(f'Inserting {NUM_NOTIFICATIONS} notifications...')

notifications_inserted = 0

for _ in range(NUM_NOTIFICATIONS):
    user_type = random.choices(
        ['Patient', 'Doctor', 'Billing'],
        weights=[70, 25, 5]
    )[0]

    if user_type == 'Patient':
        user_id = random.choice(patient_ids)
    elif user_type == 'Doctor':
        user_id = random.choice(doctor_ids)
    else:
        # Billing notifications aren't tied to a person in our schema,
        # so we point them at a patient_id as a placeholder reference.
        user_id = random.choice(patient_ids)

    title, message = random.choice(NOTIFICATION_TEMPLATES)
    is_read = random.choices([0, 1], weights=[35, 65])[0]

    cursor.execute(
        '''
        INSERT INTO notification (user_type, user_id, title, message, is_read)
        VALUES (%s, %s, %s, %s, %s)
        ''',
        (user_type, user_id, title, message, is_read)
    )
    notifications_inserted += 1

connection.commit()
print(f'  Done. Inserted {notifications_inserted} notifications.')

# ─── STEP 8: INSERT ACTIVITY LOG ENTRIES ────────────────────────────────────
# activity_log is append-only, so this simulates realistic audit trail data.
print(f'Inserting {NUM_ACTIVITY_LOGS} activity log entries...')

logs_inserted = 0
target_tables = ['patient', 'appointment', 'billing', 'prescription', 'report']

for _ in range(NUM_ACTIVITY_LOGS):
    user_type = random.choices(
        ['Doctor', 'Patient', 'Billing'],
        weights=[50, 30, 20]
    )[0]

    if user_type == 'Doctor':
        user_id = random.choice(doctor_ids)
    else:
        user_id = random.choice(patient_ids)

    action       = random.choice(LOG_ACTIONS)
    target_table = random.choice(target_tables)
    target_id    = random.randint(1, 3000)
    ip_address   = fake.ipv4()

    old_value = None
    new_value = None
    if action == 'UPDATE_BILL_STATUS':
        old_value = random.choice(['Pending', 'Partially Paid'])
        new_value = random.choice(['Paid', 'Rejected'])
    elif action == 'SOFT_DELETE_PATIENT':
        old_value = 'is_deleted=0'
        new_value = 'is_deleted=1'

    logged_at = datetime.now() - timedelta(
        days=random.randint(0, 730),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59)
    )

    cursor.execute(
        '''
        INSERT INTO activity_log
            (user_type, user_id, action, target_table, target_id,
             old_value, new_value, ip_address, logged_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''',
        (user_type, user_id, action, target_table, target_id,
         old_value, new_value, ip_address, logged_at)
    )
    logs_inserted += 1

connection.commit()
print(f'  Done. Inserted {logs_inserted} activity log entries.')

# ─── STEP 9: VERIFY ROW COUNTS ──────────────────────────────────────────────
print()
print('=== FINAL ROW COUNTS ===')

all_tables = [
    'doctor', 'patient', 'appointment', 'billing',
    'prescription', 'notification', 'report', 'activity_log'
]

for table in all_tables:
    cursor.execute(f'SELECT COUNT(*) FROM {table}')
    count = cursor.fetchone()[0]
    print(f'  {table:15s}: {count} rows')

# ─── CLEANUP ────────────────────────────────────────────────────────────────
cursor.close()
connection.close()
print()
print('Done. caresync_pro database is fully populated.')