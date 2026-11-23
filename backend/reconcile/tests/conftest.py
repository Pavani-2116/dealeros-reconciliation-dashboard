import pytest
from django.conf import settings

from reconcile.importer import run_import


@pytest.fixture
def real_data(db):
    """Load the three ORIGINAL csv files from backend/data into the test database."""
    return run_import(settings.DATA_DIR)
