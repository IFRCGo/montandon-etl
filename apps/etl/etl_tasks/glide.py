from datetime import date, datetime, timedelta

from celery import shared_task

from apps.etl.extraction.sources.glide.extract import (
    GlideExtraction,
    GlideExtractionMetadata,
    GlideExtractionMetadataType,
    GlideExtractionParamsMetadata,
)
from apps.etl.models import ExtractionData, HazardType
from main.celery import CeleryQueue
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


def _init_glide_extraction(hazard_type: HazardType, from_date: date, to_date: date):
    GlideExtraction.init_extraction(
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
        queue_name=CeleryQueue.EXTRACTION,
    )


def _ext_and_transform_glide_historical_data(hazard_type: HazardType, start_date: date, end_date: date):
    to_date = end_date

    while start_date < to_date:
        # chunks a long date range into 1-year slices
        chunk_end = start_date.replace(year=start_date.year + 1) - timedelta(days=1)
        if chunk_end > to_date:
            chunk_end = to_date

        _init_glide_extraction(hazard_type, start_date, chunk_end)
        start_date = chunk_end + timedelta(days=1)


@shared_task
def ext_and_transform_glide_latest_data():
    to_date = datetime.today().date()

    for hazard_type in GLIDE_HAZARDS:
        ext_object = (
            ExtractionData.objects.filter(
                source=ExtractionData.Source.GLIDE,
                status=ExtractionData.Status.SUCCESS,
                metadata__params__events=hazard_type.value,
                resp_data__isnull=False,
            )
            .only("id", "created_at")
            .order_by("-created_at")
            .first()
        )

        from_date = ext_object.created_at.date() if ext_object else etl_config.GLIDE_START_DATE
        _init_glide_extraction(hazard_type, from_date, to_date)


@shared_task
def ext_and_transform_glide_historical_data(start_date: date, end_date: date):
    for hazard_type in GLIDE_HAZARDS:
        _ext_and_transform_glide_historical_data(hazard_type, start_date, end_date)
