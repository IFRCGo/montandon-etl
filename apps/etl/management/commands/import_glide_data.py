import logging
from django.core.management.base import BaseCommand

from apps.etl.models import HazardType
from apps.etl.glide_task import import_glide_hazard_data

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Import data from glide api"

    def handle(self, *args, **options):
        print("Importing Glide data")
        import_glide_hazard_data.delay("EQ", HazardType.EARTHQUAKE)
        # import_hazard_data.delay("TC", HazardType.CYCLONE)
        # import_hazard_data.delay("FL", HazardType.FLOOD)
        # import_hazard_data.delay("DR", HazardType.DROUGHT)
        # import_hazard_data.delay("WF", HazardType.WILDFIRE)
        # import_hazard_data.delay("VO", HazardType.VOLCANO)
        # import_hazard_data.delay("TS", HazardType.TSUNAMI)
