import logging

from django.core.management.base import BaseCommand

from apps.etl.etl_tasks.usgs import import_usgs_data
from apps.etl.transform.sources.usgs import transform_usgs_event_data

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Import data from usgs"

    def handle(self, *args, **options):
        data = import_usgs_data()
        transform_usgs_event_data(data)
