import logging

from django.core.management.base import BaseCommand

from apps.etl.etl_tasks.glide import import_glide_hazard_data
from apps.etl.models import HazardType

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Import data from glide api"

    def handle(self, *args, **options):
        import_glide_hazard_data.delay("EQ", HazardType.EARTHQUAKE)
        import_glide_hazard_data.delay("TC", HazardType.CYCLONE)
        import_glide_hazard_data.delay("FL", HazardType.FLOOD)
        import_glide_hazard_data.delay("DR", HazardType.DROUGHT)
        import_glide_hazard_data.delay("WF", HazardType.WILDFIRE)
        import_glide_hazard_data.delay("VO", HazardType.VOLCANO)
        import_glide_hazard_data.delay("TS", HazardType.TSUNAMI)
        import_glide_hazard_data.delay("CW", HazardType.COLDWAVE)
        import_glide_hazard_data.delay("CE", HazardType.COMPLEX_EMERGENCY)
        import_glide_hazard_data.delay("EP", HazardType.EPIDEMIC)
        import_glide_hazard_data.delay("EC", HazardType.EXTRATROPICAL_CYCLONE)
        import_glide_hazard_data.delay("ET", HazardType.EXTREME_TEMPERATURE)
        import_glide_hazard_data.delay("FA", HazardType.FAMINE)
        import_glide_hazard_data.delay("FR", HazardType.FIRE)
        import_glide_hazard_data.delay("FF", HazardType.FLASH_FLOOD)
        import_glide_hazard_data.delay("HT", HazardType.HEAT_WAVE)
        import_glide_hazard_data.delay("IN", HazardType.INSECT_INFESTATION)
        import_glide_hazard_data.delay("LS", HazardType.LANDSLIDE)
        import_glide_hazard_data.delay("MS", HazardType.MUD_SLIDE)
        import_glide_hazard_data.delay("ST", HazardType.SEVERE_LOCAL_STROM)
        import_glide_hazard_data.delay("SL", HazardType.SLIDE)
        import_glide_hazard_data.delay("AV", HazardType.SNOW_AVALANCHE)
        import_glide_hazard_data.delay("SS", HazardType.STORM)
        import_glide_hazard_data.delay("AC", HazardType.TECH_DISASTER)
        import_glide_hazard_data.delay("TO", HazardType.TORNADO)
        import_glide_hazard_data.delay("VW", HazardType.VIOLENT_WIND)
        import_glide_hazard_data.delay("WV", HazardType.WAVE_SURGE)
