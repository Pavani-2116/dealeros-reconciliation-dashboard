from datetime import date
from decimal import Decimal

import pytest

from reconcile.cleaning import normalize_ref, parse_amount, parse_date


@pytest.mark.parametrize('raw, expected', [
    ('REC-1034', 'REC-1034'),
    ('rec1034', 'REC-1034'),
    (' REC - 1070 ', 'REC-1070'),
    ('1112', 'REC-1112'),
    ('', None),
    (None, None),
    ('no digits', None),
])
def test_normalize_ref(raw, expected):
    assert normalize_ref(raw) == expected


def test_indian_style_commas_are_parsed():
    assert parse_amount('1,25,400.00') == Decimal('125400.00')


@pytest.mark.parametrize('raw', ['', '   ', None, 'abc', 'NaN', 'Infinity'])
def test_blank_or_junk_amount_is_none_never_zero(raw):
    assert parse_amount(raw) is None


def test_amount_is_decimal_not_float():
    assert isinstance(parse_amount('0.1'), Decimal)
    assert parse_amount('0.1') + parse_amount('0.2') == Decimal('0.3')


def test_parse_date():
    assert parse_date('2026-03-24') == date(2026, 3, 24)
    assert parse_date('') is None
    assert parse_date('24/03/2026') is None
