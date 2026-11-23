"""Pure reconciliation logic. No database, no web code, no organisations.

Inputs are plain dicts so the rules are easy to read and to unit-test:

    a_rows : {record_id: {'total': Decimal|None, 'location': str|None,
                          'date': date|None, 'state': 'CONFIRMED'|'VOIDED'}}
    b_rows : [{'entry_id': str, 'ref': str, 'value': Decimal|None,
               'location': str|None, 'date': date|None}]     (ref already cleaned)

Output is a list of `Disagreement` objects. Rules, in plain words:

MISSING_IN_B    An A record has no B entry at all.
ORPHAN_IN_B     A B entry points at a record that is not in A.
DUPLICATE_IN_B  One record has several B entries whose values do NOT add up to
                A's total. If they add up exactly it is a split and is fine.
VALUE_MISMATCH  B's value differs from A's total_value (NOT base_value).
                A blank B value is "unknown", so it is flagged too (never 0).
LOCATION_MISMATCH / DATE_MISMATCH   (extra) a 1-to-1 matched pair differs.
VOIDED_IN_A     (extra) A says VOIDED but B still has an entry for it.
                A VOIDED record is otherwise skipped: its absence from B is
                expected, so it is never reported as MISSING_IN_B.
"""
from dataclasses import dataclass
from decimal import Decimal

MISSING_IN_B = 'MISSING_IN_B'
ORPHAN_IN_B = 'ORPHAN_IN_B'
DUPLICATE_IN_B = 'DUPLICATE_IN_B'
VALUE_MISMATCH = 'VALUE_MISMATCH'
LOCATION_MISMATCH = 'LOCATION_MISMATCH'
DATE_MISMATCH = 'DATE_MISMATCH'
VOIDED_IN_A = 'VOIDED_IN_A'

ALL_REASONS = (MISSING_IN_B, ORPHAN_IN_B, DUPLICATE_IN_B, VALUE_MISMATCH,
               LOCATION_MISMATCH, DATE_MISMATCH, VOIDED_IN_A)


@dataclass(frozen=True)
class Disagreement:
    reason: str
    record_id: str                 # A's record id (or the B reference for an orphan)
    entry_ids: tuple = ()          # the B entries involved, in order
    in_a: bool = True              # False for an orphan (no A record exists)
    a_location: str = None
    a_value: Decimal = None
    b_locations: tuple = ()        # one per entry, same order as entry_ids
    b_values: tuple = ()           # one per entry; None = blank/unknown


def _group_by_ref(b_rows):
    grouped = {}
    for entry in b_rows:
        grouped.setdefault(entry['ref'], []).append(entry)
    return grouped


def _make(reason, record_id, a=None, entries=()):
    return Disagreement(
        reason=reason,
        record_id=record_id,
        entry_ids=tuple(e['entry_id'] for e in entries),
        in_a=a is not None,
        a_location=a['location'] if a else None,
        a_value=a['total'] if a else None,
        b_locations=tuple(e['location'] for e in entries),
        b_values=tuple(e['value'] for e in entries),
    )


def _compare_one_record(record_id, a, entries):
    """Apply the rules to one A record and the B entries that point at it."""
    if a['state'] == 'VOIDED':
        # Decision: voided + still in B is a disagreement; voided + not in B is expected.
        return [_make(VOIDED_IN_A, record_id, a, entries)] if entries else []

    if not entries:
        return [_make(MISSING_IN_B, record_id, a)]

    values = [e['value'] for e in entries]
    # Blank/unknown anywhere (on either side) cannot be confirmed equal. Never treat as 0.
    if a['total'] is None or any(v is None for v in values):
        return [_make(VALUE_MISMATCH, record_id, a, entries)]

    if len(entries) > 1:
        # A split that adds up exactly is fine; anything else is a duplicate.
        if sum(values) != a['total']:
            return [_make(DUPLICATE_IN_B, record_id, a, entries)]
        return []

    entry, found = entries[0], []
    if entry['value'] != a['total']:
        found.append(_make(VALUE_MISMATCH, record_id, a, entries))
    # Unknown (None) locations/dates are not treated as differences.
    if None not in (entry['location'], a['location']) and entry['location'] != a['location']:
        found.append(_make(LOCATION_MISMATCH, record_id, a, entries))
    if None not in (entry['date'], a['date']) and entry['date'] != a['date']:
        found.append(_make(DATE_MISMATCH, record_id, a, entries))
    return found


def compare(a_rows, b_rows):
    """Return every disagreement between System A and System B."""
    by_ref = _group_by_ref(b_rows)
    found = []
    for ref, entries in by_ref.items():
        if ref not in a_rows:
            found += [_make(ORPHAN_IN_B, ref, None, [e]) for e in entries]  # one row per orphan entry
    for record_id, a in a_rows.items():
        found += _compare_one_record(record_id, a, by_ref.get(record_id, []))
    return found
