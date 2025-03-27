import datetime
import json
from datetime import datetime as dt

import requests
import requests_cache
from celery import chain, shared_task
from celery.utils.log import get_task_logger

from apps.etl.extraction.sources.gdacs.extract import (
    GdacsEventExtractionInputMetadata,
    GdacsExtraction,
    GdacsExtractionInputMetadata,
)
from apps.etl.models import ExtractionData, HazardType
from apps.etl.transform.sources.gdacs import GDACSTransformHandler
from main.configs import etl_config
from main.logging import log_extra

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
def extract_and_transform_data(url, metadata, input_metadata_class):
    try:
        parent_extraction_id = GdacsExtraction.task(
            url=URL, metadata=metadata, input_metadata_class=GdacsExtractionInputMetadata
        )
        hazard_type = metadata["eventlist"]

        if parent_extraction_id:
            base_instance = ExtractionData.objects.get(id=parent_extraction_id)
            base_response_data = json.loads(base_instance.resp_data.read())

            for feature in base_response_data["features"]:
                event_id = feature["properties"]["eventid"]
                event_detail_url = f"{etl_config.GDACS_URL}/gdacsapi/api/events/geteventdata"
                event_params = GdacsEventExtractionInputMetadata(eventtype=hazard_type, eventid=event_id, episodeid=None)

                event_detail_base_extraction_id = GdacsExtraction.task(
                    url=event_detail_url,
                    metadata=event_params.model_dump(),
                    parent_id=base_instance.id,
                    input_metadata_class=GdacsEventExtractionInputMetadata,
                )

                chain(extract.s(event_detail_base_extraction_id), GDACSTransformHandler.task.s()).apply_async()

    except requests.exceptions.RequestException:
        logger.error(
            "Extraction failed",
            exc_info=True,
            extra=log_extra({"metadata": metadata}),
        )


@shared_task
def extract(extraction_object_id):
    """
    Import hazard data from gdacs api
    """
    event_instance = ExtractionData.objects.get(id=extraction_object_id)
    event_response_data = json.loads(event_instance.resp_data.read())

    for episode_data in event_response_data["properties"]["episodes"]:
        event_episode_url = episode_data["details"]
        event_episode_extraction_id = GdacsExtraction.handle_extraction(
            params=None,
            url=event_episode_url,
            parent_id=event_instance.id,
            source=ExtractionData.Source.GDACS,
            headers={"accept": "application/json"},
        )
        event_episode_instance_id = ExtractionData.objects.get(id=event_episode_extraction_id)
        event_episode_response_data = json.loads(event_episode_instance_id.resp_data.read())

        geometry_episode_url = event_episode_response_data["properties"]["url"]["geometry"]
        GdacsExtraction.handle_extraction(
            params=None,
            url=geometry_episode_url,
            parent_id=event_episode_instance_id.id,
            source=ExtractionData.Source.GDACS,
            headers={"accept": "application/json"},
        )

        return event_instance.id


@shared_task
def _ext_and_transform_gdacs_latest_data(hazard: HazardType, size):
    from apps.etl.etl_tasks.run_gdacs_historical import deep_dive

    ext_object = (
        ExtractionData.objects.filter(
            source=ExtractionData.Source.GDACS,
            hazard_type=hazard,
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

    deep_dive(session, hazard, start_date, end_date, size, "")


@shared_task
def ext_and_transform_gdacs_latest_data():
    for hazard, size in HAZARDS:
        _ext_and_transform_gdacs_latest_data(hazard, size)


@shared_task
def ext_and_transform_gdacs_historical_data():
    from apps.etl.etl_tasks.run_gdacs_historical import deep_dive

    start_date = datetime.date(2000, 1, 1)
    end_date = datetime.date(2025, 1, 1)
    for hazard, size in HAZARDS:
        deep_dive(session, hazard, start_date, end_date, size, "")
