import logging

from django.core.management.base import BaseCommand

from apps.etl.etl_tasks.gdacs import ext_and_transform_gdacs_historical_data
from apps.etl.models import HazardType

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Import data from gdacs api"

    def handle(self, *args, **options):
        ext_and_transform_gdacs_historical_data("EQ", HazardType.EARTHQUAKE)
        ext_and_transform_gdacs_historical_data("TC", HazardType.CYCLONE)
        ext_and_transform_gdacs_historical_data("FL", HazardType.FLOOD)
        ext_and_transform_gdacs_historical_data("DR", HazardType.DROUGHT)
        ext_and_transform_gdacs_historical_data("WF", HazardType.WILDFIRE)
        ext_and_transform_gdacs_historical_data("VO", HazardType.VOLCANO)
        ext_and_transform_gdacs_historical_data("TS", HazardType.TSUNAMI)
