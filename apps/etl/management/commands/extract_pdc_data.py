import logging

from django.core.management.base import BaseCommand

# TODO we need to extract command from etl_tasks
from apps.etl.extraction.sources.pdc.extract import import_hazard_data
from apps.etl.models import HazardType

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Import data from pdc api"

    def handle(self, *args, **options):
        import_hazard_data()
