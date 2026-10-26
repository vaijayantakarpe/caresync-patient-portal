# ============================================================
# FILE: exceptions.py
# PURPOSE: Custom exceptions for hospital AI system
# ============================================================


class AlreadyDischargedError(Exception):
    """
    Raised when trying to discharge
    a patient who is already discharged.
    """
    pass


class CriticalPatientError(Exception):
    """
    Raised when trying to discharge
    a patient with critical vitals.
    """
    pass