from datetime import datetime, timedelta

from celery import shared_task

from apps.etl.extraction.sources.glide.extract import (
    GlideExtraction,
    GlideExtractionMetadata,
    GlideExtractionMetadataType,
    GlideExtractionParamsMetadata,
)
from apps.etl.models import ExtractionData, HazardType
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


def _ext_and_transform_glide_historical_data(hazard_type: HazardType):
    start_date = etl_config.GLIDE_START_DATE
    to_date = datetime.today().date()

    while start_date < to_date:
        end_date = start_date.replace(year=start_date.year + 1) - timedelta(days=1)
        if end_date > to_date:
            end_date = to_date

        extraction_object = GlideExtraction.init_extraction(
            metadata=GlideExtractionMetadata(
                url=f"{etl_config.GLIDE_URL}/glide/jsonglideset.jsp",
                params=GlideExtractionParamsMetadata(
                    fromyear=start_date.year,
                    frommonth=start_date.month,
                    fromday=start_date.day,
                    toyear=end_date.year,
                    tomonth=end_date.month,
                    today=end_date.day,
                    events=hazard_type.value,
                ),
                type=GlideExtractionMetadataType.QUERY,
            ),
            add_to_queue=False,
        )

        GlideExtraction.task.delay(extraction_object.id)
        start_date = end_date + timedelta(days=1)


@shared_task
def ext_and_transform_glide_latest_data():
    ext_object = (
        ExtractionData.objects.filter(
            source=ExtractionData.Source.GLIDE,
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

    for hazard_type in GLIDE_HAZARDS:
        extraction_object = GlideExtraction.init_extraction(
            metadata=GlideExtractionMetadata(
                url=f"{etl_config.GLIDE_URL}/glide/jsonglideset.jsp",
                params=GlideExtractionParamsMetadata(
                    fromyear=from_date.year,
                    frommonth=from_date.month,
                    fromday=from_date.day,
                    toyear=to_date.year,
                    tomonth=to_date.month,
                    today=to_date.day,
                    events=hazard_type.value,
                ),
                type=GlideExtractionMetadataType.QUERY,
            ),
            add_to_queue=False,
        )
        GlideExtraction.task.delay(extraction_object.id)


@shared_task
def ext_and_transform_glide_historical_data():
    for hazard_type in GLIDE_HAZARDS:
        _ext_and_transform_glide_historical_data(hazard_type)
