import hashlib
import json
import logging
from datetime import datetime, timedelta

import requests
from celery import shared_task
from celery.exceptions import MaxRetriesExceededError
from django.core.files.base import ContentFile
from django.core.management import call_command
from pydantic import ValidationError

from apps.etl.extract import Extraction
from apps.etl.extraction_validators.gdacs_events_validator import (
    GdacsEventsDataValidator,
)
from apps.etl.extraction_validators.gdacs_eventsdata_geometry_validator import (
    GdacsEventsGeometryData,
)
from apps.etl.models import ExtractionData
from apps.etl.transformer import transform_1, transform_2, transform_3

logger = logging.getLogger(__name__)


@shared_task
def fetch_gdacs_data():
    call_command("import_gdacs_data")


def retry_fetch_data(self, url):
    response = None  # Initialize response variable
    try:
        gdacs_extraction = Extraction(url=url)
        response = gdacs_extraction.pull_data(source=ExtractionData.Source.GDACS)
    except requests.exceptions.RequestException as exc:
        self.retry(exc=exc)

    return response


def validate_source_data(resp_data):
    try:
        resp_data_for_validation = json.loads(resp_data.decode("utf-8"))
        GdacsEventsDataValidator(**resp_data_for_validation)
        validation_error = ""
    except ValidationError as e:
        validation_error = e.json()
    validation_data = {
        "status": ExtractionData.ValidationStatus.FAILED if validation_error else ExtractionData.ValidationStatus.SUCCESS,
        "validation_error": validation_error if validation_error else "",
    }
    return validation_data


def validate_gdacs_geometry_data(resp_data):
    try:
        resp_data_for_validation = json.loads(resp_data.decode("utf-8"))
        GdacsEventsGeometryData(**resp_data_for_validation)
        validation_error = ""
    except ValidationError as e:
        validation_error = e.json()
    validation_data = {
        "status": ExtractionData.ValidationStatus.FAILED if validation_error else ExtractionData.ValidationStatus.SUCCESS,
        "validation_error": validation_error if validation_error else "",
    }
    return validation_data


def manage_duplicate_file_content(source, hash_content, instance, response_data, file_name):
    duplicate_file_content = ExtractionData.objects.filter(source=source, file_hash=hash_content)
    if duplicate_file_content:
        instance.resp_data = duplicate_file_content.first().resp_data
    else:
        instance.resp_data.save(file_name, ContentFile(response_data))
    instance.save()


def hash_file_content(content):
    """
    Compute the hash of a file using the specified algorithm.
    :return: Hexadecimal hash of the file
    """
    file_hash = hashlib.sha256(content).hexdigest()
    return file_hash


@shared_task(bind=True, max_retries=2, default_retry_delay=5)
def scrape_population_exposure_data(self, parent_id, event_id: int, hazard_type: str, parent_transform_id):
    url = f"https://www.gdacs.org/report.aspx?eventid={event_id}&eventtype={hazard_type}"

    response = retry_fetch_data(self, url)
    resp_data = response.pop("resp_data")
    file_extension = response.pop("file_extension")
    file_name = f"gdacs_footprint.{file_extension}"
    gdacs_instance = ExtractionData.objects.create(**response, parent=ExtractionData.objects.get(id=parent_id))
    if resp_data:
        resp_data_content = resp_data.content
        # TODO Source validation
        # duplicate file content check
        hash_content = hash_file_content(resp_data_content)
        manage_duplicate_file_content(
            source=ExtractionData.Source.GDACS,
            hash_content=hash_content,
            instance=gdacs_instance,
            response_data=resp_data_content,
            file_name=file_name,
        )
        transform_3.delay(parent_transform_id)


@shared_task(bind=True, max_retries=2, default_retry_delay=5)
def fetch_gdacs_geometry_data(self, parent_id, footprint_url, parent_transform_id):
    response = retry_fetch_data(self, footprint_url)
    resp_data = response.pop("resp_data")
    file_extension = response.pop("file_extension")
    file_name = f"gdacs_footprint.{file_extension}"
    gdacs_instance = ExtractionData.objects.create(**response, parent=ExtractionData.objects.get(id=parent_id))
    if resp_data:
        resp_data_content = resp_data.content
        # Source validation
        gdacs_instance.source_validation_status = validate_gdacs_geometry_data(resp_data_content)["status"]
        gdacs_instance.content_validation = validate_gdacs_geometry_data(resp_data_content)["validation_error"]

        # duplicate file content check
        hash_content = hash_file_content(resp_data_content)
        manage_duplicate_file_content(
            source=ExtractionData.Source.GDACS,
            hash_content=hash_content,
            instance=gdacs_instance,
            response_data=resp_data_content,
            file_name=file_name,
        )
        transform_2.delay(parent_transform_id)


@shared_task(bind=True, max_retries=2, default_retry_delay=5)
def import_hazard_data(self, hazard_type, hazard_type_str):
    print(f"Importing {hazard_type} data")
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    gdacs_url = f"https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH?eventlist={hazard_type}&fromDate={yesterday}&toDate={today}&alertlevel=Green;Orange;Red"  # noqa: E501

    response = retry_fetch_data(self, gdacs_url)
    print("RESP", response)

    file_extension = response.pop("file_extension")
    file_name = f"gdacs.{file_extension}"
    resp_data = response.pop("resp_data")
    gdacs_instance = ExtractionData.objects.create(
        **response,
    )
    if resp_data:
        resp_data_content = resp_data.content
        # Source validation
        gdacs_instance.source_validation_status = validate_source_data(resp_data_content)["status"]
        gdacs_instance.content_validation = validate_source_data(resp_data_content)["validation_error"]

        # duplicate file content check
        hash_content = hash_file_content(resp_data_content)
        manage_duplicate_file_content(
            source=ExtractionData.Source.GDACS,
            hash_content=hash_content,
            instance=gdacs_instance,
            response_data=resp_data_content,
            file_name=file_name,
        )

    transform_id = None
    if (
        gdacs_instance.resp_code == 200
        and gdacs_instance.status == ExtractionData.Status.SUCCESS
        and gdacs_instance.resp_data
    ):
        transform = transform_1.delay("test")
        transform_id = transform.id
        print("Trandform 1 id", transform_id)

        for feature in resp_data.json()["features"]:
            event_id = feature["properties"]["eventid"]
            episode_id = feature["properties"]["episodeid"]
            footprint_url = feature["properties"]["url"]["geometry"]
            # if hazard_type == HazardType.CYCLONE:
            #     footprint_url = f"https://www.gdacs.org/contentdata/resources/{hazard_type_str}/{event_id}/geojson_{event_id}_{episode_id}.geojson"  # noqa: E501

            # fetch geometry data
            fetch_gdacs_geometry_data.delay(gdacs_instance.id, footprint_url, transform_id)

            # fetch population exposure data
            scrape_population_exposure_data.delay(gdacs_instance.id, event_id, hazard_type, transform_id)

    print(f"{hazard_type} data imported sucessfully")
