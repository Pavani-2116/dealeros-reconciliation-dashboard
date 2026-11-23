"""One test per kind of disagreement, plus the things that look wrong but are fine.

These tests call the pure `compare` function directly (no database).
"""
from datetime import date
from decimal import Decimal

from reconcile.cleaning import normalize_ref
from reconcile.compare import (DATE_MISMATCH, DUPLICATE_IN_B, LOCATION_MISMATCH, MISSING_IN_B,
                               ORPHAN_IN_B, VALUE_MISMATCH, VOIDED_IN_A, compare)


def a_rec(total='100.00', location='L1', day=date(2026, 3, 1), state='CONFIRMED'):
    return {'total': None if total is None else Decimal(total), 'location': location,
            'date': day, 'state': state}


def b_entry(entry_id='E1', ref='REC-1', value='100.00', location='L1', day=date(2026, 3, 1)):
    return {'entry_id': entry_id, 'ref': ref, 'location': location, 'date': day,
            'value': None if value is None else Decimal(value)}


def reasons(found):
    return sorted((d.reason, d.record_id) for d in found)


def test_clean_row_has_no_disagreement():
    assert compare({'REC-1': a_rec()}, [b_entry()]) == []


def test_missing_in_b():
    assert reasons(compare({'REC-1': a_rec()}, [])) == [(MISSING_IN_B, 'REC-1')]


def test_orphan_in_b():
    found = compare({'REC-1': a_rec()}, [b_entry(), b_entry('E9', ref='REC-999')])
    assert reasons(found) == [(ORPHAN_IN_B, 'REC-999')]
    assert found[0].in_a is False and found[0].entry_ids == ('E9',)


def test_same_amount_entered_twice_is_a_duplicate():
    found = compare({'REC-1': a_rec()}, [b_entry('E1'), b_entry('E2')])
    assert reasons(found) == [(DUPLICATE_IN_B, 'REC-1')]


def test_split_that_sums_to_total_is_not_an_error():
    b = [b_entry('E1', value='40.00'), b_entry('E2', value='60.00')]
    assert compare({'REC-1': a_rec()}, b) == []


def test_split_that_does_not_sum_is_a_duplicate():
    b = [b_entry('E1', value='40.00'), b_entry('E2', value='59.99')]
    assert reasons(compare({'REC-1': a_rec()}, b)) == [(DUPLICATE_IN_B, 'REC-1')]


def test_split_is_exact_not_float_rounded():
    # 0.1 + 0.2 must equal 0.3 exactly, which is why we use Decimal.
    b = [b_entry('E1', value='0.10'), b_entry('E2', value='0.20')]
    assert compare({'REC-1': a_rec(total='0.30')}, b) == []


def test_value_mismatch():
    found = compare({'REC-1': a_rec()}, [b_entry(value='99.00')])
    assert reasons(found) == [(VALUE_MISMATCH, 'REC-1')]


def test_b_is_compared_with_total_not_base_value():
    # B holding only the base amount (total = base + adjustment) is a mismatch.
    a = a_rec(total='121.00')
    assert reasons(compare({'REC-1': a}, [b_entry(value='94.00')])) == [(VALUE_MISMATCH, 'REC-1')]


def test_blank_b_value_is_flagged_and_not_treated_as_zero():
    found = compare({'REC-1': a_rec()}, [b_entry(value=None)])
    assert reasons(found) == [(VALUE_MISMATCH, 'REC-1')]
    assert found[0].b_values == (None,)  # still unknown, not Decimal('0')


def test_blank_b_value_matches_a_zero_total_only_if_known():
    # Even when A's total is 0, an UNKNOWN B value must not be read as 0 and pass.
    found = compare({'REC-1': a_rec(total='0.00')}, [b_entry(value=None)])
    assert reasons(found) == [(VALUE_MISMATCH, 'REC-1')]


def test_blank_value_inside_multiple_entries_is_flagged_as_value_mismatch():
    b = [b_entry('E1', value='40.00'), b_entry('E2', value=None)]
    assert reasons(compare({'REC-1': a_rec()}, b)) == [(VALUE_MISMATCH, 'REC-1')]


def test_unknown_a_total_cannot_be_confirmed():
    assert reasons(compare({'REC-1': a_rec(total=None)}, [b_entry()])) == [(VALUE_MISMATCH, 'REC-1')]


def test_messy_references_match_their_records_and_are_not_flagged():
    a_rows = {'REC-1034': a_rec(), 'REC-1070': a_rec(), 'REC-1112': a_rec()}
    b = [b_entry('E1', ref=normalize_ref('rec1034')),
         b_entry('E2', ref=normalize_ref(' REC - 1070 ')),
         b_entry('E3', ref=normalize_ref('1112'))]
    assert compare(a_rows, b) == []


def test_location_mismatch():
    found = compare({'REC-1': a_rec()}, [b_entry(location='L2')])
    assert reasons(found) == [(LOCATION_MISMATCH, 'REC-1')]


def test_date_mismatch():
    found = compare({'REC-1': a_rec()}, [b_entry(day=date(2026, 3, 3))])
    assert reasons(found) == [(DATE_MISMATCH, 'REC-1')]


def test_voided_record_still_in_b_is_flagged():
    assert reasons(compare({'REC-1': a_rec(state='VOIDED')}, [b_entry()])) == [(VOIDED_IN_A, 'REC-1')]


def test_voided_record_missing_from_b_is_expected():
    assert compare({'REC-1': a_rec(state='VOIDED')}, []) == []
