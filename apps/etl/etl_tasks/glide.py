from datetime import datetime

from celery import chain, shared_task

from apps.etl.extraction.sources.glide.extract import GlideExtraction, GlideExtractionMetadata
from apps.etl.models import ExtractionData, HazardType
from apps.etl.transform.sources.glide import GlideTransformHandler
from main.configs import etl_config

GLIDE_HAZARDS = [
    HazardType.EARTHQUAKE,
    HazardType.FLOOD,
    HazardType.CYCLONE,
    HazardType.EPIDEMIC,
    HazardType.STORM,
    HazardType.DROUGHT,
    HazardType.TSUNAMI,
    HazardType.WILDFIRE,
    HazardType.VOLCANO,
    HazardType.COLDWAVE,
    HazardType.EXTRATROPICAL_CYCLONE,
    HazardType.EXTREME_TEMPERATURE,
    HazardType.FIRE,
    HazardType.FLASH_FLOOD,
    HazardType.HEAT_WAVE,
    HazardType.INSECT_INFESTATION,
    HazardType.LANDSLIDE,
    HazardType.MUD_SLIDE,
    HazardType.SEVERE_LOCAL_STROM,
    HazardType.SLIDE,
    HazardType.SNOW_AVALANCHE,
    HazardType.TECH_DISASTER,
    HazardType.TORNADO,
    HazardType.VIOLENT_WIND,
    HazardType.WAVE_SURGE,
]


@shared_task
def _ext_and_transform_glide_latest_data(hazard_type: HazardType):
    ext_object = (
        ExtractionData.objects.filter(
            source=ExtractionData.Source.GLIDE,
            hazard_type=hazard_type,
            status=ExtractionData.Status.SUCCESS,
            resp_data__isnull=False,
        )
        .order_by("-created_at")
        .first()
    )

    if ext_object:
        from_date = ext_object.created_at.date()
    else:
        from_date = etl_config.GLIDE_START_DATE

    to_date = datetime.today().date()

    # FIXME: Check if the date filters are inclusive
    metadata = GlideExtractionMetadata(
        fromyear=from_date.year,
        frommonth=from_date.month,
        fromday=from_date.day,
        toyear=to_date.year,
        tomonth=to_date.month,
        today=to_date.day,
        events=hazard_type.value,
    )

    extraction_id = GlideExtraction().create_extraction_instance(source=ExtractionData.Source.GLIDE, metadata=metadata)

    chain(
        GlideExtraction.task.s(extraction_id),
        GlideTransformHandler.task.s(),
    ).apply_async()


@shared_task
def _ext_and_transform_glide_historical_data(hazard_type: HazardType):
    to_date = datetime.today().date()

    # FIXME: Check if the date filters are inclusive
    metadata = GlideExtractionMetadata(
        fromyear=None,
        frommonth=None,
        fromday=None,
        toyear=to_date.year,
        tomonth=to_date.month,
        today=to_date.day,
        events=hazard_type.value,
    )

    extraction_id = GlideExtraction().create_extraction_instance(source=ExtractionData.Source.GLIDE, metadata=metadata)

    chain(
        GlideExtraction.task.s(extraction_id),
        GlideTransformHandler.task.s(),
    ).apply_async()


@shared_task
def ext_and_transform_glide_latest_data():
    for hazard_type in GLIDE_HAZARDS:
        _ext_and_transform_glide_latest_data(hazard_type)


@shared_task
def ext_and_transform_glide_historical_data():
    for hazard_type in GLIDE_HAZARDS:
        _ext_and_transform_glide_historical_data(hazard_type)
