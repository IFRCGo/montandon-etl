import datetime
from datetime import datetime as dt

import requests_cache
from celery import shared_task
from celery.utils.log import get_task_logger

from apps.etl.models import ExtractionData, HazardType
from main.configs import etl_config

logger = get_task_logger(__name__)

session = requests_cache.CachedSession(
    "gdacs_request",
    expire_after=-1,
    allowable_codes=[200, 204],
)

HAZARDS = [
    (HazardType.EARTHQUAKE, 64),
    (HazardType.CYCLONE, 64),
    (HazardType.FLOOD, 64),
    (HazardType.DROUGHT, 64),
    (HazardType.WILDFIRE, 64),
    (HazardType.VOLCANO, 64),
    (HazardType.TSUNAMI, 64),
]

URL = f"{etl_config.GDACS_URL}/gdacsapi/api/events/geteventlist/SEARCH"


@shared_task
def ext_and_transform_gdacs_latest_data():
    from apps.etl.etl_tasks.segment_gdacs import deep_dive

    ext_object = (
        ExtractionData.objects.filter(
            source=ExtractionData.Source.GDACS,
            status=ExtractionData.Status.SUCCESS,
            resp_data__isnull=False,
        )
        .order_by("-created_at")
        .first()
    )
    if ext_object:
        start_date = ext_object.created_at.date()
        if start_date < etl_config.GDACS_START_DATE:
            start_date = etl_config.GDACS_START_DATE
    else:
        start_date = etl_config.GDACS_START_DATE

    end_date = dt.today().date()
    for hazard, size in HAZARDS:
        deep_dive(session, hazard, start_date, end_date, size, "")


@shared_task
def ext_and_transform_gdacs_historical_data(start_date: datetime.datetime, end_date: datetime.datetime):
    from apps.etl.etl_tasks.segment_gdacs import deep_dive

    for hazard, size in HAZARDS:
        deep_dive(session, hazard, start_date, end_date, size, "")
