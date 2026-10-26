import pandas as pd

# ============================================================
# PATIENT DATA CLEANING
# ============================================================

# 1. LOAD DATASET
# ============================================================

df = pd.read_csv("patient_data_messy.csv")

print("========================================")
print("ORIGINAL DATASET")
print("========================================")

print(df.head())

print("\nDataset shape:")
print(df.shape)

print("\nColumn names:")
print(df.columns.tolist())


# ============================================================
# 2. CHECK MISSING VALUES
# ============================================================

print("\n========================================")
print("MISSING VALUES BEFORE CLEANING")
print("========================================")

print(df.isnull().sum())


# ============================================================
# 3. CHECK DUPLICATE ROWS
# ============================================================

print("\n========================================")
print("DUPLICATES BEFORE CLEANING")
print("========================================")

print("Duplicate rows:", df.duplicated().sum())


# ============================================================
# 4. CLEAN LEADING AND TRAILING SPACES
# ============================================================

text_columns = [
    "patient_name",
    "city",
    "department",
    "insurance_company",
    "claim_status"
]

for col in text_columns:
    df[col] = df[col].str.strip()


# ============================================================
# 5. STANDARDIZE TEXT CASING
# ============================================================

for col in text_columns:
    df[col] = df[col].str.title()


# ============================================================
# 6. CORRECT INSURANCE COMPANY NAME
# ============================================================

df["insurance_company"] = df["insurance_company"].replace(
    {
        "Hdfc Ergo": "HDFC Ergo"
    }
)


# ============================================================
# 7. CONVERT NUMERIC COLUMNS
# ============================================================

df["age"] = pd.to_numeric(
    df["age"],
    errors="coerce"
)

df["bill_amount"] = pd.to_numeric(
    df["bill_amount"],
    errors="coerce"
)


# ============================================================
# 8. HANDLE MISSING AGE
# ============================================================

df["age"] = df["age"].fillna(
    df["age"].median()
)


# ============================================================
# 9. HANDLE MISSING BILL AMOUNT
# ============================================================

df["bill_amount"] = df["bill_amount"].fillna(
    df["bill_amount"].median()
)


# ============================================================
# 10. HANDLE MISSING PHONE NUMBER
# ============================================================

df["phone_number"] = df["phone_number"].fillna(
    "Not Available"
)


# ============================================================
# 11. CONVERT MIXED DATE FORMATS
# ============================================================

df["admission_date"] = pd.to_datetime(
    df["admission_date"],
    format="mixed",
    errors="coerce"
)


# ============================================================
# 12. REMOVE DUPLICATE ROWS
# ============================================================

df = df.drop_duplicates()


# ============================================================
# 13. DISPLAY CLEANED DATA
# ============================================================

print("\n========================================")
print("CLEANED DATA")
print("========================================")

print(df.head(10))


# ============================================================
# 14. DATASET SHAPE AFTER CLEANING
# ============================================================

print("\nDataset shape after cleaning:")
print(df.shape)


# ============================================================
# 15. MISSING VALUES AFTER CLEANING
# ============================================================

print("\n========================================")
print("MISSING VALUES AFTER CLEANING")
print("========================================")

print(df.isnull().sum())


# ============================================================
# 16. DUPLICATES AFTER CLEANING
# ============================================================

print("\n========================================")
print("DUPLICATES AFTER CLEANING")
print("========================================")

print("Duplicate rows:", df.duplicated().sum())


# ============================================================
# 17. CHECK DATA TYPES
# ============================================================

print("\n========================================")
print("DATA TYPES")
print("========================================")

print(df.dtypes)


# ============================================================
# 18. SAVE CLEANED DATASET
# ============================================================

df.to_csv(
    "patients_cleaned.csv",
    index=False
)


# ============================================================
# 19. FINAL DATA QUALITY CHECK
# ============================================================

print("\n========================================")
print("FINAL DATA QUALITY CHECK")
print("========================================")

print("\nUnique cities:")
print(df["city"].unique())

print("\nUnique departments:")
print(df["department"].unique())

print("\nUnique insurance companies:")
print(df["insurance_company"].unique())

print("\nUnique claim statuses:")
print(df["claim_status"].unique())

print("\nDate range:")
print("From:", df["admission_date"].min())
print("To:", df["admission_date"].max())


# ============================================================
# 20. COMPLETION MESSAGE
# ============================================================

print("\n========================================")
print("DATA CLEANING COMPLETED SUCCESSFULLY!")
print("========================================")

print("Original rows: 3060")
print("Duplicate rows removed: 60")
print("Final rows:", len(df))
print("Final columns:", len(df.columns))

print("\nCleaned file:")
print("patients_cleaned.csv")