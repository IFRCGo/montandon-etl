import datetime
from datetime import datetime as dt

import requests_cache
from celery import chain, shared_task
from celery.utils.log import get_task_logger

from apps.etl.extraction.sources.gdacs.extract import (
    GdacsExtraction,
    GdacsExtractionMetadata,
    GdacsExtractionMetadataType,
    GdacsExtractionParamsMetadata,
)
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
def gdacs_init_extraction(params_list):
    for params_dict in params_list:
        GdacsExtraction.init_extraction(
            metadata=GdacsExtractionMetadata(
                params=GdacsExtractionParamsMetadata(
                    fromDate=str(params_dict.get("iter_date")),
                    toDate=str(params_dict.get("session_end_date")),
                    alertlevel="Green;Orange;Red",
                    eventlist=params_dict.get("hazard"),
                    country=None,
                ),
                url=URL,
                type=GdacsExtractionMetadataType.QUERY,
            ),
        )


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
    else:
        start_date = etl_config.GDACS_START_DATE

    end_date = dt.today().date()
    for hazard, size in HAZARDS:
        chain(deep_dive.si(session, hazard, start_date, end_date, size, ""), gdacs_init_extraction.s()).apply_async()


@shared_task
def ext_and_transform_gdacs_historical_data():
    from apps.etl.etl_tasks.segment_gdacs import deep_dive

    start_date = datetime.date(2000, 1, 1)
    end_date = datetime.date(2025, 1, 1)
    for hazard, size in HAZARDS:
        chain(deep_dive.si(session, hazard, start_date, end_date, size, ""), gdacs_init_extraction.s()).apply_async()
