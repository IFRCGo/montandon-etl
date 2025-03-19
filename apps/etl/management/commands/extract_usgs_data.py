import logging

from django.core.management.base import BaseCommand

# from apps.etl.etl_tasks.usgs import ext_and_transform_usgs_latest_data
from apps.etl.etl_tasks.usgs import ext_and_transform_usgs_historical_data

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Import data from usgs"

    def handle(self, *args, **options):
        """Handler"""
        ext_and_transform_usgs_historical_data()
