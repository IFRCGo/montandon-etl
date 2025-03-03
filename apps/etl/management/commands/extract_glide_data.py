import logging

from django.core.management.base import BaseCommand

from apps.etl.etl_tasks.glide import ext_and_transform_glide_historical_data

from apps.etl.models import HazardType

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Import data from glide api"

    def handle(self, *args, **options):
        ext_and_transform_glide_historical_data.delay("EQ", HazardType.EARTHQUAKE)
        ext_and_transform_glide_historical_data.delay("TC", HazardType.CYCLONE)
        ext_and_transform_glide_historical_data.delay("FL", HazardType.FLOOD)
        ext_and_transform_glide_historical_data.delay("DR", HazardType.DROUGHT)
        ext_and_transform_glide_historical_data.delay("WF", HazardType.WILDFIRE)
        ext_and_transform_glide_historical_data.delay("VO", HazardType.VOLCANO)
        ext_and_transform_glide_historical_data.delay("TS", HazardType.TSUNAMI)
        ext_and_transform_glide_historical_data.delay("CW", HazardType.COLDWAVE)
        ext_and_transform_glide_historical_data.delay("EP", HazardType.EPIDEMIC)
        ext_and_transform_glide_historical_data.delay("EC", HazardType.EXTRATROPICAL_CYCLONE)
        ext_and_transform_glide_historical_data.delay("ET", HazardType.EXTREME_TEMPERATURE)
        ext_and_transform_glide_historical_data.delay("FR", HazardType.FIRE)
        ext_and_transform_glide_historical_data.delay("FF", HazardType.FLASH_FLOOD)
        ext_and_transform_glide_historical_data.delay("HT", HazardType.HEAT_WAVE)
        ext_and_transform_glide_historical_data.delay("IN", HazardType.INSECT_INFESTATION)
        ext_and_transform_glide_historical_data.delay("LS", HazardType.LANDSLIDE)
        ext_and_transform_glide_historical_data.delay("MS", HazardType.MUD_SLIDE)
        ext_and_transform_glide_historical_data.delay("ST", HazardType.SEVERE_LOCAL_STROM)
        ext_and_transform_glide_historical_data.delay("SL", HazardType.SLIDE)
        ext_and_transform_glide_historical_data.delay("AV", HazardType.SNOW_AVALANCHE)
        ext_and_transform_glide_historical_data.delay("SS", HazardType.STORM)
        ext_and_transform_glide_historical_data.delay("AC", HazardType.TECH_DISASTER)
        ext_and_transform_glide_historical_data.delay("TO", HazardType.TORNADO)
        ext_and_transform_glide_historical_data.delay("VW", HazardType.VIOLENT_WIND)
        ext_and_transform_glide_historical_data.delay("WV", HazardType.WAVE_SURGE)
