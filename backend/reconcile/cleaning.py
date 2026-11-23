"""Small, pure helpers that turn messy CSV text into clean values.

No database or Django code here, so each function is trivial to unit-test.
The golden rule: if we cannot understand a value we return None. We NEVER
invent a value (in particular never 0) for something we could not read.
"""
import re
from datetime import date
from decimal import Decimal, InvalidOperation


def clean_text(raw):
    """Strip spaces from a CSV cell. A missing cell becomes ''."""
    return (raw or '').strip()


def normalize_ref(raw):
    """'rec1034', ' REC - 1070 ', '1112' -> 'REC-1034', 'REC-1070', 'REC-1112'.

    Takes the first run of digits and rebuilds the canonical form.
    Returns None when there are no digits at all.
    """
    match = re.search(r'\d+', raw or '')
    return f'REC-{match.group()}' if match else None


def parse_amount(raw):
    """'1,25,400.00' -> Decimal('125400.00').  Blank or junk -> None (never 0).

    Commas (Indian-style or western) and spaces are removed before parsing.
    'NaN' / 'Infinity' are valid for Decimal() but are not money, so they are
    treated as junk.
    """
    text = (raw or '').strip().replace(',', '').replace(' ', '')
    if not text:
        return None
    try:
        value = Decimal(text)
    except InvalidOperation:
        return None
    return value if value.is_finite() else None


def parse_date(raw):
    """'2026-03-24' -> date(2026, 3, 24).  Blank or invalid -> None."""
    try:
        return date.fromisoformat((raw or '').strip())
    except ValueError:
        return None
