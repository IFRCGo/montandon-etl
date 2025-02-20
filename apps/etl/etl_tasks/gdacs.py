import json
import logging
from datetime import datetime, timedelta

import requests
from celery import chain, shared_task

from apps.etl.extraction.sources.base.extract import Extraction
from apps.etl.extraction.sources.base.utils import store_extraction_data
from apps.etl.extraction.sources.gdacs.extract import (
    fetch_event_data,
    fetch_gdacs_geometry_data,
    validate_source_data,
)
from apps.etl.models import ExtractionData, HazardType
from apps.etl.transform.sources.gdacs import (
    transform_event_data,
    transform_geo_data,
    transform_impact_data,
)

logger = logging.getLogger(__name__)


def ext_and_transform_gdacs_latest_data(hazard_type: str, hazard_type_str: str):
    ext_object = (
        ExtractionData.objects.filter(
            source=ExtractionData.Source.GDACS,
            hazard_type=hazard_type,
            status=ExtractionData.Status.SUCCESS,
            resp_data__isnull=False,
        )
        .order_by("-created_at")
        .first()
    )

    if ext_object:
        # if old data exists , pull the latest data.
        from_date = ext_object.created_at.date()
        to_date = datetime.now().date()
        ext_and_transform_gdacs_data.delay(hazard_type, hazard_type_str, from_date, to_date)
    else:
        # pull old data
        ext_and_transform_gdacs_historical_data(hazard_type, hazard_type_str)


def ext_and_transform_gdacs_historical_data(hazard_type: str, hazard_type_str: str):
    # Start from 2000
    start_year = 2000
    end_year = datetime.now().year

    current_date = datetime(start_year, 1, 1)
    end_date = datetime(end_year, 12, 31)

    while current_date <= end_date:
        month_start = current_date.strftime("%Y-%m-%d")
        month_end = (current_date + timedelta(days=31)).replace(day=1) - timedelta(days=1)
        month_end = month_end.strftime("%Y-%m-%d")

        ext_and_transform_gdacs_data.delay(hazard_type, hazard_type_str, month_start, month_end)

        current_date += timedelta(days=31)
        current_date = current_date.replace(day=1)


@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def ext_and_transform_gdacs_data(self, hazard_type: str, hazard_type_str: str, from_date: str, to_date: str, **kwargs):
    """
    Import hazard data from gdacs api
    """
    logger.info(f"Importing {hazard_type} data")

    gdacs_url = f"https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH?eventlist={hazard_type}&fromDate={from_date}&toDate={to_date}&alertlevel=Green;Orange;Red"  # noqa: E501

    # Create a Extraction object in the begining
    instance_id = kwargs.get("instance_id", None)
    retry_count = kwargs.get("retry_count", None)

    gdacs_instance = (
        ExtractionData.objects.get(id=instance_id)
        if instance_id
        else ExtractionData.objects.create(
            source=ExtractionData.Source.GDACS,
            status=ExtractionData.Status.PENDING,
            source_validation_status=ExtractionData.ValidationStatus.NO_VALIDATION,
            hazard_type=hazard_type_str,
            attempt_no=0,
            resp_code=0,
        )
    )

    # Extract the data from api.
    gdacs_extraction = Extraction(url=gdacs_url)
    response = None
    try:
        response = gdacs_extraction.pull_data(
            source=ExtractionData.Source.GDACS,
            ext_object_id=gdacs_instance.id,
            retry_count=retry_count if retry_count else 1,
        )
    except requests.exceptions.RequestException as exc:
        self.retry(exc=exc, kwargs={"instance_id": gdacs_instance.id, "retry_count": self.request.retries})

    if response:
        resp_data_content = response["resp_data"].content

        # decode the byte object(response data) into json
        try:
            resp_data_json = json.loads(resp_data_content.decode("utf-8"))
        except json.JSONDecodeError as e:
            logger.info(f"JSON decode error: {e}")
            resp_data_json = {}

        # Save the extracted data into the existing gdacs object
        gdacs_instance = store_extraction_data(
            source=ExtractionData.Source.GDACS,
            response=response,
            validate_source_func=validate_source_data,
            instance_id=gdacs_instance.id,
        )

        # Fetch geometry and population exposure data
        if gdacs_instance.resp_code == 200 and gdacs_instance.status == ExtractionData.Status.SUCCESS and resp_data_json:
            for feature in resp_data_json["features"]:
                event_id = feature["properties"]["eventid"]
                episode_id = feature["properties"]["episodeid"]
                footprint_url = feature["properties"]["url"]["geometry"]
                if hazard_type == HazardType.CYCLONE and event_id and episode_id:
                    footprint_url = f"https://www.gdacs.org/contentdata/resources/{hazard_type_str}/{event_id}/geojson_{event_id}_{episode_id}.geojson"  # noqa: E501

                event_workflow = chain(
                    fetch_event_data.s(
                        parent_id=gdacs_instance.id,
                        event_id=event_id,
                        hazard_type=hazard_type,
                    ),
                    transform_event_data.s(),
                )
                event_result = event_workflow.apply_async()

                geo_workflow = chain(
                    fetch_gdacs_geometry_data.s(
                        parent_id=gdacs_instance.id,
                        footprint_url=footprint_url,
                    ),
                    transform_geo_data.s(event_result.parent.id),
                )
                geo_workflow.apply_async()

                impact_workflow = chain(
                    fetch_event_data.s(
                        parent_id=gdacs_instance.id,
                        event_id=event_id,
                        hazard_type=hazard_type,
                    ),
                    transform_impact_data.s(),
                )
                impact_workflow.apply_async()

        logger.info(f"{hazard_type} data imported sucessfully")
