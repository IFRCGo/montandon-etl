import logging

from django.core.management.base import BaseCommand

from apps.etl.etl_tasks.pdc import ext_and_transform_pdc_historical_data

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Import data from pdc api"

    def handle(self, *args, **options):
        ext_and_transform_pdc_historical_data.delay()
