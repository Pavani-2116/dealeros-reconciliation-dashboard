# Decisions

Each entry explains what I chose, what alternatives I rejected, and why. These decisions reflect the current application implementation.

## 1. Compare System B's `value` with System A's `total_value`

- **Chosen:** Compare System B's `value` with System A's `total_value`.
- **Rejected:** Comparing with `base_value`.
- **Reason:** `total_value` equals `base_value + adjustment` across all 120 System A records. System B matches `total_value` for the corresponding records. Comparing against `base_value` would incorrectly flag many records.

  REC-1003 demonstrates why this matters: System B contains the same amount as System A's `base_value` (94,834.38), but System A's `total_value` is 121,388.01. Therefore, the record is correctly identified as a value mismatch.

## 2. Normalise record references using the first sequence of digits

- **Chosen:** Extract the first sequence of digits from a reference and rebuild it in the `REC-####` format.
- **Rejected:** Exact string matching or guessing an organisation or record from ID patterns.
- **Reason:** System B contains inconsistent reference formats, such as `rec1034`, `REC - 1070`, and `1112`. The `normalize_ref` function converts these into a consistent `REC-####` format.

  The original reference is preserved in `record_ref_raw`, so the imported source data is not lost.

  If a reference contains no digits, the cleaned reference is stored as NULL. Such an entry cannot match a System A record and is handled as an orphan.

## 3. Treat blank or unreadable monetary values as NULL, never zero

- **Chosen:** Store blank or unreadable monetary values as NULL.
- **Rejected:** Replacing missing or invalid values with zero.
- **Reason:** Zero is a valid monetary amount, whereas a blank value means the amount is unknown. Treating an unknown amount as zero could produce incorrect comparisons.

  The importer stores the cleaned value as NULL and preserves the original text in `value_raw`.

  During comparison, an unknown value cannot be confirmed as equal to another amount, so it is reported as `VALUE_MISMATCH`. REC-1050 demonstrates this behaviour.

  The same rule applies when one entry in a group of multiple System B entries has a blank value or when System A's total is unreadable.

  Indian-style monetary values such as `1,25,400.00` are parsed as `125400.00` before comparison. However, REC-1064 remains a genuine mismatch because System A's total is 183,244.16. Normalising the number format does not make unequal amounts equal.

## 4. Treat multiple System B entries as a valid split only when their sum matches System A's total

- **Chosen:** Allow multiple System B entries when their combined value exactly matches System A's `total_value`.
- **Rejected:** Flagging every record that has more than one System B entry.
- **Reason:** Multiple entries may represent a legitimate split rather than a duplicate.

  REC-1055 contains two entries, 71,950.93 and 107,926.39. Their sum equals System A's total of 179,877.32, so the record is treated as a valid split and is not flagged.

  REC-1042 contains the same amount twice. Its combined value does not equal System A's total, so it is reported as `DUPLICATE_IN_B`.

  The comparison uses exact Decimal arithmetic rather than relying on entry labels. For records with multiple entries, the implementation checks the combined amount. Location and date comparisons are performed only for one-to-one record pairs.

## 5. Handle VOIDED records as a separate disagreement

- **Chosen:** Report a System A record marked `VOIDED` that still has a corresponding System B entry as `VOIDED_IN_A`. A VOIDED record without a System B entry is considered expected.
- **Rejected:** Ignoring VOIDED records or treating a corresponding System B entry as acceptable.
- **Reason:** If System A has cancelled a record but System B still contains it, the two systems disagree. REC-1019 demonstrates this case.

  A VOIDED record is not reported as `MISSING_IN_B` because the absence of a corresponding System B entry is expected.

  No additional value or date checks are performed for VOIDED records because those details are not meaningful for a cancelled record.

  This is an additional disagreement type beyond the four required types. It is a business-rule interpretation that can be changed in `compare.py`.

## 6. Report date and location differences as separate disagreement types

- **Chosen:** Report date and location differences using `DATE_MISMATCH` and `LOCATION_MISMATCH`.
- **Rejected:** Ignoring these differences or combining them with `VALUE_MISMATCH`.
- **Reason:** The supplied data includes deliberate date and location differences, such as REC-1009 and REC-1077.

  Keeping these reasons separate makes the disagreements easier to understand and allows users to filter them independently.

  If a date or location is NULL on either side, it is not treated as a confirmed difference.

## 7. Show cross-organisation mismatches only to the organisation that owns the System A record

- **Chosen:** Show REC-1077 only to ORG-A, with System B details hidden.
- **Rejected:** Showing ORG-B's location details to ORG-A or displaying the same disagreement to both organisations.
- **Reason:** REC-1077 belongs to an ORG-A location in System A, but its System B entry refers to an ORG-B location.

  Showing the ORG-B location to ORG-A would expose another organisation's information. Therefore:

  - ORG-A can see the disagreement.
  - ORG-A sees its own System A location.
  - System B's location, value, and entry IDs are hidden.
  - `b_details_hidden` is set to `true`.
  - ORG-B does not see the row because the original System A record belongs to ORG-A.

  The general rule implemented in `services.py` is that a disagreement belongs to the organisation owning the System A record. For an orphan entry, ownership is determined using the organisation of the System B entry's own location.

  System B details associated with another organisation's location are not exposed.

  The trade-off is that ORG-A can see that a location disagreement exists without seeing the other organisation's location details.

## 8. Apply organisation filtering inside database queries

- **Chosen:** Require every API request to specify a valid organisation and filter records inside the database query.
- **Rejected:** Loading all records and hiding other organisations' rows in React, or guessing organisation ownership from location ID patterns.
- **Reason:** Hiding records only in the frontend does not protect the underlying data because users could still inspect API responses in the browser's network tools.

  System A records are retrieved using organisation-filtered queries such as `location__org_id=<org>`. Organisation ownership is obtained from the `Location` table, which is populated using `locations.csv`.

  Missing or unknown organisation parameters return HTTP 400.

  An automated test checks that the organisation condition is included in the database query.

  **Limitation:** The application does not implement authentication. The API currently trusts the `org` parameter. In a production application, organisation access should be determined using the authenticated user's permissions.

## 9. Use SQLite and Decimal for the assessment

- **Chosen:** Use SQLite for the database and Decimal for monetary calculations.
- **Rejected:** Using PostgreSQL for this assessment or using floating-point numbers for money.
- **Reason:** SQLite is included with Python and Django, making the application easier for reviewers to set up without configuring an external database. It is suitable for the relatively small supplied dataset.

  Monetary calculations use Python's `Decimal` type and Django's `DecimalField` to maintain precision.

  For example, floating-point arithmetic can produce precision errors when adding values such as 0.1 and 0.2. Decimal arithmetic represents these monetary values accurately.

  The API also returns monetary values as exact text, such as `"183244.16"`, rather than as floating-point JSON numbers.