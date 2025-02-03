import json
import logging

import requests
from celery import chain, shared_task

from apps.etl.extraction.sources.base.extract import Extraction
from apps.etl.extraction.sources.base.utils import store_extraction_data
from apps.etl.models import ExtractionData, HazardType
from apps.etl.transform.sources.usgs import transform_usgs_event_data

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def fetch_detail(self, parent_id, detail_url, **kwargs):
    url = detail_url
    instance_id = kwargs.get("instance_id", None)
    if not instance_id:
        usgs_instance = ExtractionData.objects.create(
            source=ExtractionData.Source.USGS,
            status=ExtractionData.Status.PENDING,
            source_validation_status=ExtractionData.ValidationStatus.NO_VALIDATION,
            attempt_no=0,
            resp_code=0,
            hazard_type=HazardType.EARTHQUAKE,
        )
    else:
        usgs_instance = ExtractionData.objects.get(id=instance_id)

    usgs_extraction = Extraction(url=url)
    response = None
    try:
        response = usgs_extraction.pull_data(
            source=ExtractionData.Source.USGS,
            ext_object_id=usgs_instance.id,
            retry_count=0,
        )
    except Exception as exc:
        self.retry(exc=exc, kwargs={"instance_id": usgs_instance.id, "retry_count": self.request.retries})
    if response:
        usgs_instance = store_extraction_data(
            response=response,
            source=ExtractionData.Source.USGS,
            instance_id=usgs_instance.id,
            parent_id=parent_id,
            hazard_type=HazardType.EARTHQUAKE,
        )
        return usgs_instance.id


@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def import_hazard_data(self, **kwargs):
    """
    Import hazard data from usgs api
    """
    logger.info(f"Importing {HazardType.EARTHQUAKE} data")

    usgs_url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson"  # noqa: E501

    # Create a Extraction object in the begining
    instance_id = kwargs.get("instance_id", None)
    retry_count = kwargs.get("retry_count", None)

    usgs_instance = (
        ExtractionData.objects.get(id=instance_id)
        if instance_id
        else ExtractionData.objects.create(
            source=ExtractionData.Source.USGS,
            status=ExtractionData.Status.PENDING,
            source_validation_status=ExtractionData.ValidationStatus.NO_VALIDATION,
            hazard_type=HazardType.EARTHQUAKE,
            attempt_no=0,
            resp_code=0,
        )
    )

    # Extract the data from api.
    usgs_extraction = Extraction(url=usgs_url)
    response = None
    try:
        response = usgs_extraction.pull_data(
            source=ExtractionData.Source.USGS,
            ext_object_id=usgs_instance.id,
            retry_count=retry_count if retry_count else 1,
        )
    except requests.exceptions.RequestException as exc:
        self.retry(exc=exc, kwargs={"instance_id": usgs_instance.id, "retry_count": self.request.retries})

    if response:
        # Save the extracted data into the existing usgs object
        usgs_instance = store_extraction_data(
            response=response,
            source=ExtractionData.Source.GDACS,
            validate_source_func=None,
            instance_id=usgs_instance.id,
        )
        if usgs_instance.resp_code == 200:
            response_data = json.loads(usgs_instance.resp_data.read())
            for feature in response_data["features"]:
                chain(
                    fetch_detail.s(usgs_instance, feature["properties"]["detail"]),
                    transform_usgs_event_data.s(),
                ).apply_async()

        logger.info(f"{HazardType.EARTHQUAKE} data imported sucessfully")
        return usgs_instance.id
