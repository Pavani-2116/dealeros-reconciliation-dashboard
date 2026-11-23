"""Glue between the database and the pure `compare` function.

This is where TENANT SAFETY lives. For one organisation we:

1. Load only A records at that org's locations (filtered in the DB query).
2. Load the B entries that point at those records, wherever they are located
   (we need them to compare), plus B entries at the org's own locations that
   point at no A record at all (orphans; the org comes from B's own location).
3. Run `compare`.
4. Redact: any B entry that sits at ANOTHER org's location is never described.
   Its location and value are hidden and its id is dropped.

Records whose A side belongs to another org never get loaded for this org, so
the other org's row (and its record id) cannot appear in the response.
"""
from decimal import Decimal

from .compare import compare
from .models import Location, SystemARecord, SystemBEntry


def valid_orgs():
    return sorted(Location.objects.values_list('org_id', flat=True).distinct())


def _load_inputs(org_id):
    """Run the org-filtered DB queries. Returns (a_rows, b_rows, org_of_entry)."""
    a_qs = SystemARecord.objects.filter(location__org_id=org_id).select_related('location')
    a_rows = {
        a.record_id: {
            'total': a.total_value,
            'location': a.location.location_id if a.location else None,
            'date': a.event_date,
            'state': a.state,
        }
        for a in a_qs
    }

    # B entries about this org's A records (may physically sit at another org's location).
    about_our_records = SystemBEntry.objects.filter(record_ref__in=a_qs.values('record_id'))
    # B entries at our locations that point at NO record in A at all (true orphans).
    our_orphans = (SystemBEntry.objects.filter(location__org_id=org_id)
                   .exclude(record_ref__in=SystemARecord.objects.values('record_id')))

    entries = {e.entry_id: e for e in about_our_records.select_related('location')}
    entries.update({e.entry_id: e for e in our_orphans.select_related('location')})

    b_rows, org_of_entry = [], {}
    for e in sorted(entries.values(), key=lambda e: e.entry_id):
        b_rows.append({
            'entry_id': e.entry_id,
            'ref': e.record_ref or e.record_ref_raw,  # a ref with no digits stays visible as an orphan
            'value': e.value,
            'location': e.location.location_id if e.location else None,
            'date': e.recorded_on,
        })
        org_of_entry[e.entry_id] = e.location.org_id if e.location else None
    return a_rows, b_rows, org_of_entry


def _to_row(d, org_id, org_of_entry):
    """Turn a Disagreement into the JSON dict, hiding other orgs' B details."""
    shown = [i for i, eid in enumerate(d.entry_ids) if org_of_entry[eid] == org_id]
    b_hidden = len(shown) < len(d.entry_ids)

    b_values = [d.b_values[i] for i in shown]
    b_locations = sorted({d.b_locations[i] for i in shown if d.b_locations[i]})
    # A total is only meaningful when every entry is visible and known.
    if not d.entry_ids or b_hidden or any(v is None for v in b_values):
        b_value = None
    else:
        b_value = sum(b_values, Decimal('0'))
    # For an orphan the only location is B's own (and it is this org's by construction).
    a_value = d.a_value
    return {
        'reason': d.reason,
        'record_id': d.record_id,
        'location': d.a_location if d.in_a else (b_locations[0] if b_locations else None),
        'b_location': ', '.join(b_locations) if b_locations else None,
        'b_details_hidden': b_hidden,  # True = a B entry lives at another org's location
        'a_value': a_value,
        'b_value': b_value,
        'difference': (b_value - a_value) if (a_value is not None and b_value is not None) else None,
        'b_entry_ids': [d.entry_ids[i] for i in shown],
    }


def _money_as_text(row):
    """Send money as exact text ('83361.40'), because JSON numbers would become floats."""
    for key in ('a_value', 'b_value', 'difference'):
        if row[key] is not None:
            row[key] = format(row[key], '.2f')
    return row


def sort_rows(rows, sort):
    """Sort by A's value (B's value for orphans). Missing values always go last."""
    def value_of(row):
        return row['a_value'] if row['a_value'] is not None else row['b_value']

    rows = sorted(rows, key=lambda r: (r['reason'], r['record_id']))  # stable default order
    if sort not in ('value', '-value'):
        return rows
    known = sorted((r for r in rows if value_of(r) is not None), key=value_of, reverse=(sort == '-value'))
    return known + [r for r in rows if value_of(r) is None]


def disagreements_for_org(org_id, reason=None, sort=None):
    a_rows, b_rows, org_of_entry = _load_inputs(org_id)
    rows = []
    for d in compare(a_rows, b_rows):
        # Safety net: a row is only ever returned when this org owns its A side
        # (confirmed by the A query above) or, for an orphan, its own B entry.
        rows.append(_to_row(d, org_id, org_of_entry))
    if reason:
        rows = [r for r in rows if r['reason'] == reason]
    return [_money_as_text(r) for r in sort_rows(rows, sort)]
