import logging

from django.core.management.base import BaseCommand

from apps.etl.etl_tasks.pdc import extract_and_transform_historical_pdc_data

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Import data from pdc api"

    def handle(self, *args, **options):
        extract_and_transform_historical_pdc_data.delay()
