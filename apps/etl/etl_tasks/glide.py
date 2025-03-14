from datetime import datetime

from celery import chain, shared_task
from django.conf import settings

from apps.etl.extraction.sources.glide.extract import GlideExtraction
from apps.etl.models import ExtractionData, HazardType
from apps.etl.transform.sources.glide import GlideTransformHandler

GLIDE_HAZARDS = [
    ("EQ", HazardType.EARTHQUAKE),
    ("TC", HazardType.CYCLONE),
    ("FL", HazardType.FLOOD),
    ("DR", HazardType.DROUGHT),
    ("WF", HazardType.WILDFIRE),
    ("VO", HazardType.VOLCANO),
    ("TS", HazardType.TSUNAMI),
    ("CW", HazardType.COLDWAVE),
    ("EP", HazardType.EPIDEMIC),
    ("EC", HazardType.EXTRATROPICAL_CYCLONE),
    ("ET", HazardType.EXTREME_TEMPERATURE),
    ("FR", HazardType.FIRE),
    ("FF", HazardType.FLASH_FLOOD),
    ("HT", HazardType.HEAT_WAVE),
    ("IN", HazardType.INSECT_INFESTATION),
    ("LS", HazardType.LANDSLIDE),
    ("MS", HazardType.MUD_SLIDE),
    ("ST", HazardType.SEVERE_LOCAL_STROM),
    ("SL", HazardType.SLIDE),
    ("AV", HazardType.SNOW_AVALANCHE),
    ("SS", HazardType.STORM),
    ("AC", HazardType.TECH_DISASTER),
    ("TO", HazardType.TORNADO),
    ("VW", HazardType.VIOLENT_WIND),
    ("WV", HazardType.WAVE_SURGE),
]


@shared_task
def _ext_and_transform_glide_latest_data(hazard_type, hazard_type_str):
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
        from_date = datetime.strptime(settings.GLIDE_START_DATE, "%Y-%m-%d").date()

    to_date = datetime.today().date()
    url = f"{settings.GLIDE_URL}/glide/jsonglideset.jsp?fromyear={from_date.year}&frommonth={from_date.month}&fromday={from_date.day}&toyear={to_date.year}&tomonth={to_date.month}&today={to_date.day}&events={hazard_type}"  # noqa: E501

    chain(GlideExtraction.task.s(url), GlideTransformHandler.task.s()).apply_async()


@shared_task
def _ext_and_transform_glide_historical_data(hazard_type, hazard_type_str):
    to_date = datetime.today().date()
    url = f"{settings.GLIDE_URL}/glide/jsonglideset.jsp?toyear={to_date.year}&tomonth={to_date.month}&to_date={to_date.day}&events={hazard_type}"  # noqa: E501
    chain(GlideExtraction.task.s(url), GlideTransformHandler.task.s()).apply_async()


@shared_task
def ext_and_transform_glide_latest_data():
    for hazard_type, hazard_type_str in GLIDE_HAZARDS:
        _ext_and_transform_glide_latest_data(hazard_type, hazard_type_str)


@shared_task
def ext_and_transform_glide_historical_data():
    for hazard_type, hazard_type_str in GLIDE_HAZARDS:
        _ext_and_transform_glide_historical_data(hazard_type, hazard_type_str)
