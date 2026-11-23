"""API and tenant-isolation tests."""
import json

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from reconcile.models import Location, SystemARecord, SystemBEntry

URL = '/api/disagreements/'


@pytest.fixture
def client():
    return APIClient()


def get(client, **params):
    return client.get(URL, params)


def pairs(response):
    return sorted((r['reason'], r['record_id']) for r in response.json())


def org_locations(org):
    return set(Location.objects.filter(org_id=org).values_list('location_id', flat=True))


# ---- what the real data should produce (checked by hand against the CSVs) -------------------

def test_org_a_disagreements_on_real_data(real_data, client):
    assert pairs(get(client, org='ORG-A')) == [
        ('DUPLICATE_IN_B', 'REC-1042'), ('LOCATION_MISMATCH', 'REC-1077'), ('MISSING_IN_B', 'REC-1015'),
        ('ORPHAN_IN_B', 'REC-1999'), ('VALUE_MISMATCH', 'REC-1027'), ('VALUE_MISMATCH', 'REC-1064'),
        ('VALUE_MISMATCH', 'REC-1088')]


def test_org_b_disagreements_on_real_data(real_data, client):
    assert pairs(get(client, org='ORG-B')) == [
        ('DATE_MISMATCH', 'REC-1009'), ('MISSING_IN_B', 'REC-1061'), ('VALUE_MISMATCH', 'REC-1003'),
        ('VALUE_MISMATCH', 'REC-1050'), ('VOIDED_IN_A', 'REC-1019')]


def test_things_that_look_wrong_but_are_fine_are_not_flagged(real_data, client):
    flagged = {r['record_id'] for org in ('ORG-A', 'ORG-B') for r in get(client, org=org).json()}
    assert 'REC-1055' not in flagged   # split into 2 parts that add up to A's total
    assert 'REC-1034' not in flagged   # 'rec1034'
    assert 'REC-1070' not in flagged   # ' REC - 1070 '
    assert 'REC-1112' not in flagged   # '1112'


def test_blank_b_value_is_null_in_json(real_data, client):
    row = next(r for r in get(client, org='ORG-B').json() if r['record_id'] == 'REC-1050')
    assert row['b_value'] is None and row['difference'] is None


def test_money_is_exact_text_not_float(real_data, client):
    row = next(r for r in get(client, org='ORG-A', reason='VALUE_MISMATCH').json() if r['record_id'] == 'REC-1064')
    assert (row['a_value'], row['b_value'], row['difference']) == ('183244.16', '125400.00', '-57844.16')


def test_reason_filter_and_value_sort(real_data, client):
    rows = get(client, org='ORG-A', reason='VALUE_MISMATCH', sort='-value').json()
    assert {r['reason'] for r in rows} == {'VALUE_MISMATCH'}
    values = [float(r['a_value']) for r in rows]
    assert values == sorted(values, reverse=True)
    asc = [float(r['a_value']) for r in get(client, org='ORG-A', sort='value').json() if r['a_value']]
    assert asc == sorted(asc)


# ---- input validation -----------------------------------------------------------------------

@pytest.mark.parametrize('params', [{}, {'org': ''}, {'org': 'ORG-Z'}, {'org': 'org-a'},
                                    {'org': 'ORG-A', 'reason': 'NOPE'}, {'org': 'ORG-A', 'sort': 'x'}])
def test_bad_parameters_return_a_clear_400(real_data, client, params):
    response = get(client, **params)
    assert response.status_code == 400 and 'error' in response.json()


# ---- tenant isolation -----------------------------------------------------------------------

@pytest.mark.parametrize('org, other', [('ORG-A', 'ORG-B'), ('ORG-B', 'ORG-A')])
def test_no_data_of_the_other_org_is_returned(real_data, client, org, other):
    text = json.dumps(get(client, org=org).json())
    for location_id in org_locations(other):
        assert location_id not in text
    other_a_ids = SystemARecord.objects.filter(location__org_id=other).values_list('record_id', flat=True)
    other_b_ids = SystemBEntry.objects.filter(location__org_id=other).values_list('entry_id', flat=True)
    for secret in [*other_a_ids, *other_b_ids]:
        assert secret not in text, f'{secret} leaked to {org}'


@pytest.mark.parametrize('org', ['ORG-A', 'ORG-B'])
def test_every_returned_row_belongs_to_the_requested_org(real_data, client, org):
    mine = org_locations(org)
    for row in get(client, org=org).json():
        assert row['location'] in mine
        assert row['b_location'] is None or set(row['b_location'].split(', ')) <= mine


def test_cross_org_location_mismatch_hides_the_other_orgs_details(real_data, client):
    # REC-1077: System A says LOC-102 (ORG-A) but System B says LOC-201 (ORG-B).
    row = next(r for r in get(client, org='ORG-A').json() if r['record_id'] == 'REC-1077')
    assert row['reason'] == 'LOCATION_MISMATCH'
    assert row['location'] == 'LOC-102'
    assert row['b_location'] is None and row['b_value'] is None and row['b_entry_ids'] == []
    assert row['b_details_hidden'] is True
    assert 'LOC-201' not in json.dumps(row)


def test_cross_org_row_is_invisible_to_the_other_org(real_data, client):
    assert 'REC-1077' not in {r['record_id'] for r in get(client, org='ORG-B').json()}


def test_reverse_cross_org_case_is_also_protected(db, client):
    """A at an ORG-B location, B at an ORG-A location: only ORG-B sees it, with A-side data hidden."""
    a_loc = Location.objects.create(location_id='LB', org_id='ORG-B')
    b_loc = Location.objects.create(location_id='LA', org_id='ORG-A')
    SystemARecord.objects.create(record_id='REC-7', location=a_loc, total_value='10.00', state='CONFIRMED')
    SystemBEntry.objects.create(entry_id='E7', record_ref='REC-7', location=b_loc, value='10.00')

    seen_by_b = get(client, org='ORG-B').json()
    assert [r['reason'] for r in seen_by_b] == ['LOCATION_MISMATCH']
    assert seen_by_b[0]['b_location'] is None and 'LA' not in json.dumps(seen_by_b)
    assert get(client, org='ORG-A').json() == []


def test_orphan_org_comes_from_the_b_entrys_own_location(db, client):
    SystemBEntry.objects.create(entry_id='E1', record_ref='REC-404', value='5.00',
                                location=Location.objects.create(location_id='LB', org_id='ORG-B'))
    Location.objects.create(location_id='LA', org_id='ORG-A')
    assert [r['record_id'] for r in get(client, org='ORG-B').json()] == ['REC-404']
    assert get(client, org='ORG-A').json() == []


def test_org_filter_is_applied_in_the_database_query(real_data, client):
    """The A-records query must carry the org condition itself (not filter afterwards in Python)."""
    with CaptureQueriesContext(connection) as ctx:
        get(client, org='ORG-A')
    first_a_query = next(q['sql'] for q in ctx.captured_queries
                         if 'FROM "reconcile_systemarecord"' in q['sql'])
    assert '"reconcile_location"."org_id" = \'ORG-A\'' in first_a_query
