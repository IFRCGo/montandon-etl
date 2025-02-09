import logging

from django.conf import settings
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Load data to stac api"

    def handle(self, *args, **options):
        # NOTE: Make sure to adjust helm values `localCacheVolume.size` according to fetched data size
        # TODO: Add logic to pull data as required
        print(f"Data will be loaded to directory: {settings.LOCAL_CACHE_DATA_DIR}")
