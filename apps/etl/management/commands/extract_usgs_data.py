import logging

from django.core.management.base import BaseCommand

from apps.etl.etl_tasks.usgs import import_and_transform_usgs_data

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Import data from usgs"

    def handle(self, *args, **options):
        import_and_transform_usgs_data.delay()
