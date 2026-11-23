"""Database tables.

Three tables, mirroring the three CSV files:

* Location       - the ONLY source of "which org owns which location".
* SystemARecord  - one row per record System A saw.
* SystemBEntry   - one row per entry System B saw.

Two deliberate design choices (see DECISIONS.md):

1. Money is a DecimalField, never a float, so 0.1 + 0.2 == 0.3 exactly.
2. SystemBEntry has NO foreign key to SystemARecord. An "orphan" B entry
   points at a record that does not exist in A, and a foreign key would make
   the database reject it. Instead we keep the cleaned text reference
   (`record_ref`) and match in Python.

Every column that could be dirty is nullable, and the original row is kept
verbatim in `raw_row`, so nothing is ever lost or turned into 0.
"""
from django.db import models

MONEY = dict(max_digits=14, decimal_places=2, null=True, blank=True)


class Location(models.Model):
    location_id = models.CharField(max_length=32, unique=True)
    org_id = models.CharField(max_length=32, db_index=True)
    location_name = models.CharField(max_length=128, blank=True, default='')

    def __str__(self):
        return f'{self.location_id} ({self.org_id})'


class SystemARecord(models.Model):
    record_id = models.CharField(max_length=64, unique=True)
    # Nullable so a row with an unknown location is still kept (never dropped).
    location = models.ForeignKey(Location, null=True, blank=True,
                                 on_delete=models.SET_NULL, related_name='a_records')
    event_date = models.DateField(null=True, blank=True)
    category_code = models.CharField(max_length=32, blank=True, default='')
    actor_id = models.CharField(max_length=64, null=True, blank=True)  # blank CSV cell -> NULL
    base_value = models.DecimalField(**MONEY)
    adjustment = models.DecimalField(**MONEY)
    total_value = models.DecimalField(**MONEY)  # base + adjustment; what B is compared to
    state = models.CharField(max_length=16, blank=True, default='')  # CONFIRMED / VOIDED
    raw_row = models.JSONField(default=dict)  # the CSV row exactly as read

    def __str__(self):
        return self.record_id


class SystemBEntry(models.Model):
    entry_id = models.CharField(max_length=64, unique=True)
    record_ref_raw = models.CharField(max_length=128, blank=True, default='')  # as written in the CSV
    # Cleaned reference, e.g. 'REC-1034'. NOT unique: several entries may share one record.
    record_ref = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    location = models.ForeignKey(Location, null=True, blank=True,
                                 on_delete=models.SET_NULL, related_name='b_entries')
    recorded_on = models.DateField(null=True, blank=True)
    value_raw = models.CharField(max_length=64, blank=True, default='')  # as written in the CSV
    value = models.DecimalField(**MONEY)  # NULL means "unknown", never zero
    label = models.CharField(max_length=255, blank=True, default='')
    raw_row = models.JSONField(default=dict)

    def __str__(self):
        return self.entry_id
