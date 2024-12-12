import hashlib
import json
import logging
import typing
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
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
from apps.etl.extraction_validators.gdacs_pop_exposure_validator import (
    PopulationExposure_FL,
    PopulationExposureDR,
    PopulationExposureEQTC,
    PopulationExposureWF,
)
from apps.etl.models import ExtractionData, HazardType
from apps.etl.transformer import transform_1, transform_2, transform_3

logger = logging.getLogger(__name__)


@shared_task
def fetch_gdacs_data():
    call_command("import_gdacs_data")


def get_as_int(value: typing.Optional[str]) -> typing.Optional[int]:
    if value is None:
        return
    if value == "-":
        return
    return int(value)


def retry_fetch_data(self, url):
    response = None
    try:
        retry_count = self.request.retries
        gdacs_extraction = Extraction(url=url)
        response = gdacs_extraction.pull_data(retry_count=retry_count, source=ExtractionData.Source.GDACS)

    except Exception as exc:
        self.retry(exc=exc)

    return response


def validate_source_data(resp_data, hazard_type=None):
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


def validate_population_exposure(html_content, hazard_type=None):
    tables = pd.read_html(html_content)
    population_exposure = {}

    displacement_data_raw = tables[0].replace({np.nan: None}).to_dict()
    displacement_data = dict(
        zip(
            displacement_data_raw[0].values(),  # First column are keys
            displacement_data_raw[1].values(),  # Second column are values
        )
    )

    validation_error = ""
    try:
        if hazard_type == "EQ":
            population_exposure["exposed_population"] = displacement_data.get("Exposed Population:")
            PopulationExposureEQTC(**population_exposure)

        elif hazard_type == "TC":
            population_exposure["exposed_population"] = displacement_data.get("Exposed population")
            PopulationExposureEQTC(**population_exposure)

        elif hazard_type == "FL":
            population_exposure["death"] = get_as_int(displacement_data.get("Death:"))
            population_exposure["displaced"] = get_as_int(displacement_data.get("Displaced:"))
            PopulationExposure_FL(**population_exposure)

        elif hazard_type == "DR":
            population_exposure["impact"] = displacement_data.get("Impact:")
            PopulationExposureDR(**population_exposure)

        elif hazard_type == "WF":
            population_exposure["people_affected"] = displacement_data.get("People affected:")
            PopulationExposureWF(**population_exposure)

    except ValidationError as e:
        validation_error = e.json()

    print("POP exp", population_exposure)

    validation_data = {
        "status": ExtractionData.ValidationStatus.FAILED if validation_error else ExtractionData.ValidationStatus.SUCCESS,
        "validation_error": validation_error,
    }
    return validation_data


def validate_gdacs_geometry_data(resp_data, hazard_type=None):
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
        instance.revision_id = duplicate_file_content.first()
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


def store_extraction_data(response, validate_source_func, parent_id=None, instance_id=None, hazard_type=None):
    file_extension = response.pop("file_extension")
    file_name = f"gdacs.{file_extension}"
    resp_data = response.pop("resp_data")
    if not instance_id:
        gdacs_instance = ExtractionData.objects.create(**response, parent_id=parent_id)
    else:
        gdacs_instance = ExtractionData.objects.get(id=instance_id)
        for key, value in response.items():
            setattr(gdacs_instance, key, value)
        gdacs_instance.save()

    if resp_data and not response["resp_code"] == 204:
        resp_data_content = resp_data.content
        # Source validation
        if validate_source_func:
            gdacs_instance.source_validation_status = validate_source_func(resp_data_content, hazard_type)["status"]
            gdacs_instance.content_validation = validate_source_func(resp_data_content, hazard_type)["validation_error"]

        # duplicate file content check
        hash_content = hash_file_content(resp_data_content)
        manage_duplicate_file_content(
            source=ExtractionData.Source.GDACS,
            hash_content=hash_content,
            instance=gdacs_instance,
            response_data=resp_data_content,
            file_name=file_name,
        )
    return gdacs_instance


@shared_task(bind=True, max_retries=2, default_retry_delay=5)
def scrape_population_exposure_data(self, parent_id, event_id: int, hazard_type: str, parent_transform_id):
    url = f"https://www.gdacs.org/report.aspx?eventid={event_id}&eventtype={hazard_type}"

    gdacs_instance = Extraction(url=url)
    response = gdacs_instance.pull_data(source=ExtractionData.Source.GDACS, retry_count=0)

    gdacs_instance = store_extraction_data(
        response=response, validate_source_func=validate_population_exposure, parent_id=parent_id, hazard_type=hazard_type
    )

    if gdacs_instance.status == ExtractionData.Status.FAILED and gdacs_instance.resp_code != 200:
        response = retry_fetch_data(self, url)
        gdacs_instance = store_extraction_data(
            response=response,
            validate_source_func=validate_population_exposure,
            parent_id=parent_id,
            instance_id=gdacs_instance.id,
            hazard_type=hazard_type,
        )
    if gdacs_instance.resp_code == 200:
        transform_3.delay(parent_transform_id)


@shared_task(bind=True, max_retries=2, default_retry_delay=5)
def fetch_gdacs_geometry_data(self, parent_id, footprint_url, parent_transform_id):
    gdacs_instance = Extraction(url=footprint_url)
    response = gdacs_instance.pull_data(source=ExtractionData.Source.GDACS, retry_count=0)

    gdacs_instance = store_extraction_data(
        response=response, validate_source_func=validate_gdacs_geometry_data, parent_id=parent_id
    )

    if gdacs_instance.status == ExtractionData.Status.FAILED and gdacs_instance.resp_code != 200:
        response = retry_fetch_data(self, footprint_url)
        gdacs_instance = store_extraction_data(
            response=response, validate_source_func=validate_source_data, parent_id=parent_id, instance_id=gdacs_instance.id
        )
    if gdacs_instance.resp_code == 200:
        transform_2.delay(parent_transform_id)


@shared_task(bind=True, max_retries=None, default_retry_delay=5)
def import_hazard_data(self, hazard_type, hazard_type_str):
    print(f"Importing {hazard_type} data")
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    gdacs_url = f"https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH?eventlist={hazard_type}&fromDate={yesterday}&toDate={today}&alertlevel=Green;Orange;Red"  # noqa: E501

    gdacs_extraction = Extraction(url=gdacs_url)
    response = gdacs_extraction.pull_data(source=ExtractionData.Source.GDACS, retry_count=0)

    resp_data_content = response["resp_data"].content

    resp_data_json = b""
    try:
        resp_data_json = json.loads(resp_data_content.decode("utf-8"))
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}")

    gdacs_instance = store_extraction_data(response=response, validate_source_func=validate_source_data)

    if gdacs_instance.status == ExtractionData.Status.FAILED and gdacs_instance.resp_code != 200:
        response = retry_fetch_data(self, gdacs_url)
        store_extraction_data(response=response, validate_source_func=validate_source_data, instance_id=gdacs_instance.id)

    transform_id = None
    if (
        gdacs_instance.resp_code == 200
        and gdacs_instance.status == ExtractionData.Status.SUCCESS
        and gdacs_instance.resp_data
        and resp_data_json != b""
    ):
        transform = transform_1.delay("test")
        transform_id = transform.id

        for feature in resp_data_json["features"]:
            event_id = feature["properties"]["eventid"]
            episode_id = feature["properties"]["episodeid"]
            footprint_url = feature["properties"]["url"]["geometry"]
            if hazard_type == HazardType.CYCLONE:
                footprint_url = f"https://www.gdacs.org/contentdata/resources/{hazard_type_str}/{event_id}/geojson_{event_id}_{episode_id}.geojson"  # noqa: E501

            # fetch geometry data
            fetch_gdacs_geometry_data.delay(gdacs_instance.id, footprint_url, transform_id)

            # fetch population exposure data
            scrape_population_exposure_data.delay(gdacs_instance.id, event_id, hazard_type, transform_id)

    print(f"{hazard_type} data imported sucessfully")
