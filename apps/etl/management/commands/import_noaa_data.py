import logging

from django.core.management.base import BaseCommand

from apps.etl.etl_tasks.noaa import import_noaa_hazard_data
from apps.etl.models import HazardType

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Import data from noaa api"

    def handle(self, *args, **options):
        import_noaa_hazard_data()