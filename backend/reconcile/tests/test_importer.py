"""Importer tests: the real CSVs, plus small hand-made dirty files."""
import csv
from datetime import date
from decimal import Decimal

from reconcile.importer import run_import
from reconcile.models import Location, SystemARecord, SystemBEntry


def test_every_row_of_the_real_files_is_saved(real_data):
    s = real_data
    assert (s.locations_read, s.locations_saved) == (5, 5)
    assert (s.a_read, s.a_saved) == (120, 120)
    assert (s.b_read, s.b_saved) == (121, 121)
    assert s.errors == [] and s.all_rows_saved
    assert (Location.objects.count(), SystemARecord.objects.count(), SystemBEntry.objects.count()) == (5, 120, 121)


def test_importer_is_idempotent(real_data, settings):
    run_import(settings.DATA_DIR)  # second run
    assert (Location.objects.count(), SystemARecord.objects.count(), SystemBEntry.objects.count()) == (5, 120, 121)


def test_blank_actor_id_is_kept_as_null(real_data):
    record = SystemARecord.objects.get(record_id='REC-1050')
    assert record.actor_id is None
    assert record.total_value == Decimal('160405.85')  # the rest of the row survived


def test_blank_b_value_is_null_and_raw_text_is_kept(real_data):
    entry = SystemBEntry.objects.get(entry_id='ENT/2026/4050')
    assert entry.value is None and entry.value != 0
    assert entry.value_raw == ''


def test_indian_comma_value_is_parsed_and_raw_is_kept(real_data):
    entry = SystemBEntry.objects.get(entry_id='ENT/2026/4064')
    assert entry.value == Decimal('125400.00')
    assert entry.value_raw == '1,25,400.00'


def test_messy_references_are_cleaned_but_the_original_is_kept(real_data):
    got = {e.entry_id: (e.record_ref_raw, e.record_ref)
           for e in SystemBEntry.objects.filter(entry_id__in=['ENT/2026/4034', 'ENT/2026/4070', 'ENT/2026/4112'])}
    assert got == {
        'ENT/2026/4034': ('rec1034', 'REC-1034'),
        'ENT/2026/4070': ('REC - 1070', 'REC-1070'),  # outer spaces stripped when reading the CSV
        'ENT/2026/4112': ('1112', 'REC-1112'),
    }


def test_orphan_and_duplicate_b_entries_are_kept(real_data):
    assert SystemBEntry.objects.filter(record_ref='REC-1999').count() == 1  # orphan
    assert SystemBEntry.objects.filter(record_ref='REC-1042').count() == 2  # duplicate
    assert not SystemARecord.objects.filter(record_id='REC-1999').exists()


def test_org_mapping_comes_only_from_locations_csv(real_data):
    assert Location.objects.get(location_id='LOC-102').org_id == 'ORG-A'
    assert Location.objects.get(location_id='LOC-201').org_id == 'ORG-B'


def _write(path, header, rows):
    with open(path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def test_dirty_rows_survive_and_are_reported(db, tmp_path):
    _write(tmp_path / 'locations.csv', ['location_id', 'org_id', 'location_name'], [['L1', 'ORG-X', 'One']])
    _write(tmp_path / 'system_a.csv',
           ['record_id', 'location_id', 'event_date', 'category_code', 'actor_id', 'base_value',
            'adjustment', 'total_value', 'state'],
           [['REC-1', 'NOPE', 'not-a-date', 'C', '', 'abc', '1', '2', 'confirmed']])
    _write(tmp_path / 'system_b.csv', ['entry_id', 'record_ref', 'location_id', 'recorded_on', 'value', 'label'],
           [['E1', 'no-digits', 'L1', '2026-01-01', 'junk', 'x'], ['E2', 'REC-1', 'L1', '2026-01-01', '', 'y']])

    s = run_import(tmp_path)

    assert (s.a_read, s.a_saved, s.b_read, s.b_saved) == (1, 1, 2, 2)  # nothing dropped
    a = SystemARecord.objects.get()
    assert a.location is None and a.event_date is None and a.base_value is None and a.actor_id is None
    assert a.state == 'CONFIRMED'
    b = SystemBEntry.objects.get(entry_id='E1')
    assert b.record_ref is None and b.value is None and b.value_raw == 'junk'
    assert (s.b_unparseable_values, s.b_blank_values, s.unknown_locations, s.unparseable_dates) == (1, 1, 1, 1)
    assert s.errors  # problems were logged
