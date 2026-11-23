"""Counts rows, blanks, odd formats and duplicates in the three CSVs.

Run it BEFORE importing, then compare with the importer summary and the
database counts. If the numbers differ, rows were lost.

    python scripts/data_profile.py
"""
import csv
import re
import sys
from collections import Counter
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / 'backend' / 'data'


def rows(name):
    with open(DATA / name, newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def main():
    locations, a, b = rows('locations.csv'), rows('system_a.csv'), rows('system_b.csv')
    print(f'locations.csv rows: {len(locations)}')
    print(f'system_a.csv rows: {len(a)}   unique record_id: {len({r["record_id"] for r in a})}')
    print(f'system_b.csv rows: {len(b)}   unique entry_id: {len({r["entry_id"] for r in b})}')

    print('\nBlank cells per column (A):', {k: sum(1 for r in a if not r[k].strip()) for k in a[0] if any(not r[k].strip() for r in a)})
    print('Blank cells per column (B):', {k: sum(1 for r in b if not r[k].strip()) for k in b[0] if any(not r[k].strip() for r in b)})
    print('A states:', dict(Counter(r['state'] for r in a)))

    odd_refs = [r['record_ref'] for r in b if not re.fullmatch(r'REC-\d+', r['record_ref'])]
    odd_vals = [r['value'] for r in b if r['value'].strip() and not re.fullmatch(r'\d+(\.\d+)?', r['value'].strip())]
    print(f'\nB references not in REC-#### form: {len(odd_refs)} -> {odd_refs}')
    print(f'B values not plain numbers: {len(odd_vals)} -> {odd_vals}')

    refs = Counter('REC-' + re.search(r'\d+', r['record_ref']).group() for r in b if re.search(r'\d+', r['record_ref']))
    a_ids = {r['record_id'] for r in a}
    print('Records with more than one B entry:', sorted(k for k, n in refs.items() if n > 1))
    print('A records with no B entry:', sorted(a_ids - set(refs)))
    print('B references with no A record:', sorted(set(refs) - a_ids))


if __name__ == '__main__':
    sys.exit(main())
