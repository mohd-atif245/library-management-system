"""
Fine calculation service
------------------------
All fine-related business logic lives here so it can be unit-tested
independently of Flask routes or database fixtures.
"""

from datetime import datetime


def calculate_fine(due_date_str: str, return_date_str: str, rate_per_day: float) -> float:
    """
    Return the overdue fine amount in rupees.

    Parameters
    ----------
    due_date_str    : ISO date string stored in the transaction (YYYY-MM-DD HH:MM)
    return_date_str : ISO date string of the actual return moment
    rate_per_day    : fine amount per overdue day (from app config)

    Returns
    -------
    float — 0.0 if the book was returned on time, otherwise days_late * rate.
    """
    fmt = "%Y-%m-%d %H:%M"
    due_date    = datetime.strptime(due_date_str,    fmt)
    return_date = datetime.strptime(return_date_str, fmt)

    if return_date <= due_date:
        return 0.0

    days_late = (return_date - due_date).days
    # Minimum 1 day charge when late (even if only hours past midnight)
    days_late = max(days_late, 1)
    return round(days_late * rate_per_day, 2)