import hashlib
import json
import logging
from datetime import datetime, timedelta

from celery import shared_task
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

logger = logging.getLogger(__name__)


@shared_task
def fetch_gdacs_data():
    call_command("import_gdacs_data")


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


def manage_dublicate_file_content(source, hash_content, instance, response_data, file_name):
    dublicate_file_content = ExtractionData.objects.filter(source=source, file_hash=hash_content)
    if dublicate_file_content:
        instance.resp_data = dublicate_file_content.first().resp_data
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


def scrape_population_exposure_data(parent_gdacs_instance, event_id: int, hazard_type: str):
    url = f"https://www.gdacs.org/report.aspx?eventid={event_id}&eventtype={hazard_type}"
    pop_exposure_extraction = Extraction(url=url)
    response = pop_exposure_extraction.pull_data(source=ExtractionData.Source.GDACS)

    resp_data = response.pop("resp_data")
    resp_data_content = resp_data.content
    file_extension = response.pop("file_extension")
    file_name = f"gdacs_footprint.{file_extension}"

    gdacs_instance = ExtractionData(**response, parent=parent_gdacs_instance)

    # TODO Source validation

    # TODO Fix dublicate file creation
    # Dublicate file content check
    hash_content = hash_file_content(resp_data_content)
    manage_dublicate_file_content(
        source=ExtractionData.Source.GDACS,
        hash_content=hash_content,
        instance=gdacs_instance,
        response_data=resp_data_content,
        file_name=file_name,
    )


@shared_task(bind=True)
def fetch_gdacs_geometry_data(self, event_id, footprint_url, hazard_type, gdacs_instance):
    # scrape_population_exposure_data(gdacs_instance, event_id, hazard_type)

    gdacs_extraction_footprint = Extraction(url=footprint_url)
    response = gdacs_extraction_footprint.pull_data(source=ExtractionData.Source.GDACS)
    resp_data = response.pop("resp_data")
    resp_data_content = resp_data.content
    file_extension = response.pop("file_extension")
    file_name = f"gdacs_footprint.{file_extension}"
    gdacs_instance = ExtractionData(**response, parent=gdacs_instance)

    # Source validation
    gdacs_instance.source_validation_status = validate_gdacs_geometry_data(resp_data_content)["status"]
    gdacs_instance.content_validation = validate_gdacs_geometry_data(resp_data_content)["validation_error"]

    # Dublicate file content check
    hash_content = hash_file_content(resp_data_content)
    manage_dublicate_file_content(
        source=ExtractionData.Source.GDACS,
        hash_content=hash_content,
        instance=gdacs_instance,
        response_data=resp_data_content,
        file_name=file_name,
    )


@shared_task(bind=True)
def import_hazard_data(self, hazard_type, hazard_type_str):
    print(f"Importing {hazard_type} data")
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)

    # gdacs_url = f"https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH?eventlist={hazard_type}&fromDate={yesterday}&toDate={today}&alertlevel=Green;Orange;Red"  # noqa: E501
    gdacs_url = "https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH?eventlist=TC&fromDate=2024-11-30&toDate=2024-12-03&alertlevel=Green;Orange;Red"
    gdacs_extraction = Extraction(url=gdacs_url)
    response = gdacs_extraction.pull_data(source=ExtractionData.Source.GDACS)

    file_extension = response.pop("file_extension")
    file_name = f"gdacs.{file_extension}"

    resp_data = response.pop("resp_data")

    gdacs_instance = ExtractionData(
        **response,
    )

    if resp_data:
        resp_data_content = resp_data.content

        # Source validation
        gdacs_instance.source_validation_status = validate_source_data(resp_data_content)["status"]
        gdacs_instance.content_validation = validate_source_data(resp_data_content)["validation_error"]

        # Dublicate file content check
        hash_content = hash_file_content(resp_data_content)
        manage_dublicate_file_content(
            source=ExtractionData.Source.GDACS,
            hash_content=hash_content,
            instance=gdacs_instance,
            response_data=resp_data_content,
            file_name=file_name,
        )

        for feature in resp_data.json()["features"]:
            event_id = feature["properties"]["eventid"]
            episode_id = feature["properties"]["episodeid"]
            footprint_url = feature["properties"]["url"]["geometry"]
            # if hazard_type == HazardType.CYCLONE:
            #     footprint_url = f"https://www.gdacs.org/contentdata/resources/{hazard_type_str}/{event_id}/geojson_{event_id}_{episode_id}.geojson"  # noqa: E501

            fetch_gdacs_geometry_data(event_id, footprint_url, hazard_type, gdacs_instance)

    gdacs_instance.save()

    print(f"{hazard_type} data imported sucessfully")
