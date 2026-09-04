# read_data.py
# CareSync Pro Database Reader
#
# This script connects to caresync_pro and runs queries across all 8 tables
# to extract meaningful information. This pattern is the foundation of
# every backend API endpoint you will build on Day 5.

import mysql.connector
from datetime import date

# ─── DATABASE CONNECTION ────────────────────────────────────────────────────
# Best practice: In a real application, you never write the password directly
# in the code. You read it from an environment variable or a config file.
# For today's learning session, we write it directly for simplicity.
connection = mysql.connector.connect(
    host='localhost',
    port=3306,
    user='root',
    
    database='caresync_pro'
)
cursor = connection.cursor(dictionary=True)  # dictionary=True gives us column names

print('Connected to caresync_pro database.')
print('=' * 60)

# ─── QUERY 1: How many doctors in each specialisation? ──────────────────────
print()
print('QUERY 1: Doctor Count by Specialisation')
print('-' * 45)

cursor.execute(
    '''
    SELECT
        specialisation,
        COUNT(*) AS total_doctors
    FROM doctor
    WHERE is_active = 1
    GROUP BY specialisation
    ORDER BY total_doctors DESC
    '''
)

rows = cursor.fetchall()
for row in rows:
    print(f"  {row['specialisation']:<25} {row['total_doctors']} doctors")

print()

# ─── QUERY 2: Total revenue by billing status ───────────────────────────────
print('QUERY 2: Revenue Summary by Bill Status')
print('-' * 45)

cursor.execute(
    '''
    SELECT
        status,
        COUNT(*)                        AS total_bills,
        ROUND(SUM(total_amount), 2)     AS total_billed,
        ROUND(SUM(amount_paid), 2)      AS total_collected
    FROM billing
    GROUP BY status
    ORDER BY total_billed DESC
    '''
)

rows = cursor.fetchall()
for row in rows:
    print(f"  {row['status']:<15}  Bills: {row['total_bills']:>5}  "
          f"Billed: Rs {row['total_billed']:>10}  "
          f"Collected: Rs {row['total_collected']:>10}")

print()

# ─── QUERY 3: Bill rejection rate ───────────────────────────────────────────
print('QUERY 3: Bill Rejection Rate')
print('-' * 45)

cursor.execute('SELECT COUNT(*) AS total FROM billing')
total_bills = cursor.fetchone()['total']

cursor.execute("SELECT COUNT(*) AS rejected FROM billing WHERE status = 'Rejected'")
rejected_bills = cursor.fetchone()['rejected']

rejection_rate = (rejected_bills / total_bills * 100) if total_bills > 0 else 0
print(f'  Total Bills    : {total_bills}')
print(f'  Rejected Bills : {rejected_bills}')
print(f'  Rejection Rate : {rejection_rate:.2f}%')

print()

# ─── QUERY 4: Top 5 busiest doctors ─────────────────────────────────────────
print('QUERY 4: Top 5 Busiest Doctors by Appointments')
print('-' * 50)

cursor.execute(
    '''
    SELECT
        d.full_name,
        d.specialisation,
        COUNT(a.appointment_id) AS total_appointments
    FROM doctor d
    JOIN appointment a ON a.doctor_id = d.doctor_id
    WHERE a.status = 'Completed'
    GROUP BY d.doctor_id, d.full_name, d.specialisation
    ORDER BY total_appointments DESC
    LIMIT 5
    '''
)

rows = cursor.fetchall()
for i, row in enumerate(rows, start=1):
    print(f"  {i}. {row['full_name']:<30} ({row['specialisation']:<20})"
          f"  {row['total_appointments']} completed appointments")

print()

# ─── QUERY 5: Most prescribed medicines ─────────────────────────────────────
print('QUERY 5: Top 5 Most Prescribed Medicines')
print('-' * 45)

cursor.execute(
    '''
    SELECT
        medicine_name,
        COUNT(*) AS times_prescribed
    FROM prescription
    WHERE is_deleted = 0
    GROUP BY medicine_name
    ORDER BY times_prescribed DESC
    LIMIT 5
    '''
)

rows = cursor.fetchall()
for row in rows:
    print(f"  {row['medicine_name']:<25} prescribed {row['times_prescribed']} times")

print()

# ─── QUERY 6: Unread notifications by user type ─────────────────────────────
print('QUERY 6: Unread Notification Count by User Type')
print('-' * 48)

cursor.execute(
    '''
    SELECT
        user_type,
        COUNT(*) AS unread_count
    FROM notification
    WHERE is_read = 0
    GROUP BY user_type
    ORDER BY unread_count DESC
    '''
)

rows = cursor.fetchall()
for row in rows:
    print(f"  {row['user_type']:<10} {row['unread_count']} unread")

print()

# ─── QUERY 7: Most common report types ──────────────────────────────────────
print('QUERY 7: Report Count by Type')
print('-' * 45)

cursor.execute(
    '''
    SELECT
        report_type,
        COUNT(*) AS total_reports
    FROM report
    WHERE is_deleted = 0
    GROUP BY report_type
    ORDER BY total_reports DESC
    '''
)

rows = cursor.fetchall()
for row in rows:
    print(f"  {row['report_type']:<25} {row['total_reports']} reports")

print()

# ─── QUERY 8: Most frequent activity log actions ────────────────────────────
print('QUERY 8: Top 5 Most Frequent Activity Log Actions')
print('-' * 50)

cursor.execute(
    '''
    SELECT
        action,
        COUNT(*) AS times_logged
    FROM activity_log
    GROUP BY action
    ORDER BY times_logged DESC
    LIMIT 5
    '''
)

rows = cursor.fetchall()
for row in rows:
    print(f"  {row['action']:<25} {row['times_logged']} entries")

print()
print('=' * 60)
print('All queries completed successfully.')

# ─── CLEANUP ────────────────────────────────────────────────────────────────
cursor.close()
connection.close()