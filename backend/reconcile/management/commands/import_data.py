from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from reconcile.importer import run_import
from reconcile.models import Location, SystemARecord, SystemBEntry


class Command(BaseCommand):
    help = 'Import locations.csv, system_a.csv and system_b.csv into the database (safe to run twice).'

    def add_arguments(self, parser):
        parser.add_argument('--data-dir', default=str(settings.DATA_DIR),
                            help='Folder containing the three CSV files (default: backend/data)')

    def handle(self, *args, **options):
        data_dir = Path(options['data_dir'])
        missing = [n for n in ('locations.csv', 'system_a.csv', 'system_b.csv') if not (data_dir / n).exists()]
        if missing:
            raise CommandError(f'Missing CSV file(s) in {data_dir}: {", ".join(missing)}')

        summary = run_import(data_dir)
        for line in summary.lines():
            self.stdout.write(line)
        for message in summary.errors:
            self.stdout.write(self.style.WARNING(f'  - {message}'))
        self.stdout.write(
            f'Rows now in database: {Location.objects.count()} locations, '
            f'{SystemARecord.objects.count()} A records, {SystemBEntry.objects.count()} B entries')

        if not summary.all_rows_saved:
            raise CommandError('Rows read and rows saved differ - see the errors above.')
        self.stdout.write(self.style.SUCCESS('Import finished: every row read was saved.'))
