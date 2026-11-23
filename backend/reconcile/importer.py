"""CSV importer: loads the three files into the database without losing rows.

Rules (from the brief):
* Every CSV row becomes one database row, even a dirty one.
* A value we cannot understand is stored as NULL (never 0) and the original
  text is kept (`value_raw`, `record_ref_raw`, `raw_row`).
* Importing twice gives the same tables (`update_or_create` on the unique id).
* Problems are logged and counted, and the import carries on.

The management command `import_data` is a thin wrapper around `run_import`.
"""
import csv
import logging
from dataclasses import dataclass, field
from pathlib import Path

from django.db import transaction

from .cleaning import clean_text, normalize_ref, parse_amount, parse_date
from .models import Location, SystemARecord, SystemBEntry

logger = logging.getLogger(__name__)


@dataclass
class ImportSummary:
    """Counters printed at the end. 'read' must equal 'saved' for every file."""
    locations_read: int = 0
    locations_saved: int = 0
    a_read: int = 0
    a_saved: int = 0
    b_read: int = 0
    b_saved: int = 0
    a_blank_actor_id: int = 0
    a_amounts_left_empty: int = 0
    b_blank_values: int = 0
    b_unparseable_values: int = 0
    b_refs_cleaned: int = 0
    unknown_locations: int = 0
    unparseable_dates: int = 0
    errors: list = field(default_factory=list)

    def lines(self):
        return [
            f'Locations: {self.locations_read} read, {self.locations_saved} saved',
            f'A: {self.a_read} read, {self.a_saved} saved',
            f'B: {self.b_read} read, {self.b_saved} saved',
            f'A actor_id left empty (NULL): {self.a_blank_actor_id}',
            f'A amounts left empty (NULL): {self.a_amounts_left_empty}',
            f'B values left empty (NULL): {self.b_blank_values} blank + {self.b_unparseable_values} unreadable',
            f'B references cleaned: {self.b_refs_cleaned}',
            f'Unknown location codes (saved with no location): {self.unknown_locations}',
            f'Unreadable dates (saved as NULL): {self.unparseable_dates}',
            f'Errors: {len(self.errors)}',
        ]

    @property
    def all_rows_saved(self):
        return (self.locations_read == self.locations_saved
                and self.a_read == self.a_saved
                and self.b_read == self.b_saved)


def read_rows(path):
    """Yield each CSV row as a dict of stripped strings (utf-8, BOM tolerated)."""
    with open(path, newline='', encoding='utf-8-sig') as handle:
        for row in csv.DictReader(handle):
            # A short row gives None cells and a long row gives a None key; tidy both.
            yield {clean_text(k): clean_text(v) for k, v in row.items() if k is not None}


def _log_error(summary, message):
    logger.warning(message)
    summary.errors.append(message)


def import_locations(path, summary):
    for row in read_rows(path):
        summary.locations_read += 1
        if not row.get('location_id'):
            _log_error(summary, f'locations row {summary.locations_read}: empty location_id, cannot save')
            continue
        Location.objects.update_or_create(
            location_id=row['location_id'],
            defaults={'org_id': row.get('org_id', ''), 'location_name': row.get('location_name', '')},
        )
        summary.locations_saved += 1


def _lookup_location(code, locations, summary, where):
    if code in locations:
        return locations[code]
    summary.unknown_locations += 1
    _log_error(summary, f'{where}: unknown location {code!r}; saved without a location')
    return None


def _date_or_none(raw, summary, where):
    parsed = parse_date(raw)
    if parsed is None and raw:
        summary.unparseable_dates += 1
        _log_error(summary, f'{where}: unreadable date {raw!r}; saved as NULL')
    return parsed


def import_system_a(path, locations, summary):
    for row in read_rows(path):
        summary.a_read += 1
        record_id = row.get('record_id', '')
        where = f'system_a row {summary.a_read} ({record_id or "no id"})'
        if not record_id:
            _log_error(summary, f'{where}: empty record_id, cannot save')
            continue

        amounts = {name: parse_amount(row.get(name)) for name in ('base_value', 'adjustment', 'total_value')}
        summary.a_amounts_left_empty += sum(1 for v in amounts.values() if v is None)
        actor_id = row.get('actor_id') or None  # blank -> NULL, row is kept
        if actor_id is None:
            summary.a_blank_actor_id += 1

        SystemARecord.objects.update_or_create(
            record_id=record_id,
            defaults={
                'location': _lookup_location(row.get('location_id', ''), locations, summary, where),
                'event_date': _date_or_none(row.get('event_date', ''), summary, where),
                'category_code': row.get('category_code', ''),
                'actor_id': actor_id,
                'state': row.get('state', '').upper(),
                'raw_row': row,
                **amounts,
            },
        )
        summary.a_saved += 1


def import_system_b(path, locations, summary):
    for row in read_rows(path):
        summary.b_read += 1
        entry_id = row.get('entry_id', '')
        where = f'system_b row {summary.b_read} ({entry_id or "no id"})'
        if not entry_id:
            _log_error(summary, f'{where}: empty entry_id, cannot save')
            continue

        ref_raw = row.get('record_ref', '')
        ref = normalize_ref(ref_raw)
        if ref is None:
            _log_error(summary, f'{where}: reference {ref_raw!r} has no digits; saved with no cleaned reference')
        elif ref != ref_raw:
            summary.b_refs_cleaned += 1

        value_raw = row.get('value', '')
        value = parse_amount(value_raw)
        if value is None:
            if value_raw:
                summary.b_unparseable_values += 1
                _log_error(summary, f'{where}: unreadable value {value_raw!r}; saved as NULL')
            else:
                summary.b_blank_values += 1

        SystemBEntry.objects.update_or_create(
            entry_id=entry_id,
            defaults={
                'record_ref_raw': ref_raw,
                'record_ref': ref,
                'location': _lookup_location(row.get('location_id', ''), locations, summary, where),
                'recorded_on': _date_or_none(row.get('recorded_on', ''), summary, where),
                'value_raw': value_raw,
                'value': value,
                'label': row.get('label', ''),
                'raw_row': row,
            },
        )
        summary.b_saved += 1


def run_import(data_dir):
    """Import all three CSVs from `data_dir`. All-or-nothing (one transaction)."""
    data_dir = Path(data_dir)
    summary = ImportSummary()
    with transaction.atomic():
        import_locations(data_dir / 'locations.csv', summary)
        locations = {loc.location_id: loc for loc in Location.objects.all()}
        import_system_a(data_dir / 'system_a.csv', locations, summary)
        import_system_b(data_dir / 'system_b.csv', locations, summary)
    return summary
