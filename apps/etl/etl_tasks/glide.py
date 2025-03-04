from celery import chain, shared_task

from apps.etl.extraction.sources.glide.extract import (
    extract_glide_historical_data,
    extract_glide_latest_data,
)
from apps.etl.models import HazardType
from apps.etl.transform.sources.glide import transform_glide_event_data


@shared_task
def ext_and_transform_glide_historical_data(hazard_type: str, hazard_type_str: str, **kwargs):
    event_workflow = chain(
        extract_glide_historical_data.s(
            hazard_type=hazard_type,
            hazard_type_str=hazard_type_str,
        ),
        transform_glide_event_data.s(),
    )
    event_workflow.apply_async()


@shared_task
def ext_and_transform_data(hazard_type, hazard_type_str):
    event_workflow = chain(
        extract_glide_latest_data.s(
            hazard_type=hazard_type,
            hazard_type_str=hazard_type_str,
        ),
        transform_glide_event_data.s(),
    )
    event_workflow.apply_async()


@shared_task
def ext_and_transform_glide_latest_data():
    ext_and_transform_data.delay("EQ", HazardType.EARTHQUAKE)
    ext_and_transform_data.delay("TC", HazardType.CYCLONE)
    ext_and_transform_data.delay("FL", HazardType.FLOOD)
    ext_and_transform_data.delay("DR", HazardType.DROUGHT)
    ext_and_transform_data.delay("WF", HazardType.WILDFIRE)
    ext_and_transform_data.delay("VO", HazardType.VOLCANO)
    ext_and_transform_data.delay("TS", HazardType.TSUNAMI)
    ext_and_transform_data.delay("CW", HazardType.COLDWAVE)
    ext_and_transform_data.delay("EP", HazardType.EPIDEMIC)
    ext_and_transform_data.delay("EC", HazardType.EXTRATROPICAL_CYCLONE)
    ext_and_transform_data.delay("ET", HazardType.EXTREME_TEMPERATURE)
    ext_and_transform_data.delay("FR", HazardType.FIRE)
    ext_and_transform_data.delay("FF", HazardType.FLASH_FLOOD)
    ext_and_transform_data.delay("HT", HazardType.HEAT_WAVE)
    ext_and_transform_data.delay("IN", HazardType.INSECT_INFESTATION)
    ext_and_transform_data.delay("LS", HazardType.LANDSLIDE)
    ext_and_transform_data.delay("MS", HazardType.MUD_SLIDE)
    ext_and_transform_data.delay("ST", HazardType.SEVERE_LOCAL_STROM)
    ext_and_transform_data.delay("SL", HazardType.SLIDE)
    ext_and_transform_data.delay("AV", HazardType.SNOW_AVALANCHE)
    ext_and_transform_data.delay("SS", HazardType.STORM)
    ext_and_transform_data.delay("AC", HazardType.TECH_DISASTER)
    ext_and_transform_data.delay("TO", HazardType.TORNADO)
    ext_and_transform_data.delay("VW", HazardType.VIOLENT_WIND)
    ext_and_transform_data.delay("WV", HazardType.WAVE_SURGE)
