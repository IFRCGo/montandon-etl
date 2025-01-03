import hashlib
import json
import logging
import typing
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import requests
from celery import chain, shared_task
from django.core.files.base import ContentFile
from django.core.management import call_command
from pydantic import ValidationError

from apps.etl.extract import Extraction
from apps.etl.extraction_validators.gdacs_eventsdata import GDacsEventDataValidator
from apps.etl.extraction_validators.gdacs_geometry import GdacsEventsGeometryData
from apps.etl.extraction_validators.gdacs_main_source import GdacsEventSourceValidator
from apps.etl.extraction_validators.gdacs_pop_exposure import (
    GdacsPopulationExposure_FL,
    GdacsPopulationExposureDR,
    GdacsPopulationExposureEQTC,
    GdacsPopulationExposureWF,
)
from apps.etl.glide_task import import_glide_hazard_data  # noqa: F401
from apps.etl.loaders import load_data
from apps.etl.models import ExtractionData, HazardType
from apps.etl.transformer import (
    transform_event_data,
    transform_geo_data,
    transform_impact_data,
)
from apps.etl.transformers.glide_transformer import (  # noqa: F401
    transform_glide_event_data,
)

logger = logging.getLogger(__name__)


@shared_task
def fetch_glide_data():
    call_command("import_glide_data")


@shared_task
def fetch_gdacs_data():
    call_command("import_gdacs_data")


def get_as_int(value: typing.Optional[str]) -> typing.Optional[int]:
    if value is None:
        return
    if value == "-":
        return
    return int(value)


def validate_source_data(resp_data):
    try:
        resp_data_for_validation = json.loads(resp_data.decode("utf-8"))
        GdacsEventSourceValidator(**resp_data_for_validation)
        validation_error = ""
    except ValidationError as e:
        validation_error = e.json()
    validation_data = {
        "status": ExtractionData.ValidationStatus.FAILED if validation_error else ExtractionData.ValidationStatus.SUCCESS,
        "validation_error": validation_error if validation_error else "",
    }
    return validation_data


def validate_event_data(resp_data):
    try:
        resp_data_for_validation = json.loads(resp_data.decode("utf-8"))
        GDacsEventDataValidator(**resp_data_for_validation)
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
            GdacsPopulationExposureEQTC(**population_exposure)

        elif hazard_type == "TC":
            population_exposure["exposed_population"] = displacement_data.get("Exposed population")
            GdacsPopulationExposureEQTC(**population_exposure)

        elif hazard_type == "FL":
            population_exposure["death"] = get_as_int(displacement_data.get("Death:"))
            population_exposure["displaced"] = get_as_int(displacement_data.get("Displaced:"))
            GdacsPopulationExposure_FL(**population_exposure)

        elif hazard_type == "DR":
            population_exposure["impact"] = displacement_data.get("Impact:")
            GdacsPopulationExposureDR(**population_exposure)

        elif hazard_type == "WF":
            population_exposure["people_affected"] = displacement_data.get("People affected:")
            GdacsPopulationExposureWF(**population_exposure)

    except ValidationError as e:
        validation_error = e.json()

    validation_data = {
        "status": ExtractionData.ValidationStatus.FAILED if validation_error else ExtractionData.ValidationStatus.SUCCESS,
        "validation_error": validation_error,
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
    """
    if duplicate file content exists then do not create a new file, but point the url to
    the previous file.
    """
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


def store_extraction_data(
    response,
    source=None,
    validate_source_func=None,
    parent_id=None,
    instance_id=None,
    hazard_type=None,
    requires_hazard_type=False,
):
    file_extension = response.pop("file_extension")
    file_name = f"gdacs.{file_extension}"
    resp_data = response.pop("resp_data")

    # save the additional response data after the data is fetched from api.
    gdacs_instance = ExtractionData.objects.get(id=instance_id)
    for key, value in response.items():
        setattr(gdacs_instance, key, value)
    gdacs_instance.save()

    # save parent id if it is child extraction object
    if parent_id:
        gdacs_instance.parent_id = parent_id
        gdacs_instance.save(update_fields=["parent_id"])

    # Validate the non empty response data.
    if resp_data and not response["resp_code"] == 204:
        resp_data_content = resp_data.content
        # Source validation
        # if the validate function requires hazard type as argument pass it as argument else don't.
        if validate_source_func:
            if requires_hazard_type:
                gdacs_instance.source_validation_status = validate_source_func(resp_data_content, hazard_type)["status"]
                gdacs_instance.content_validation = validate_source_func(resp_data_content, hazard_type)["validation_error"]
            else:
                gdacs_instance.source_validation_status = validate_source_func(resp_data_content)["status"]
                gdacs_instance.content_validation = validate_source_func(resp_data_content)["validation_error"]

        # manage duplicate file content.
        hash_content = hash_file_content(resp_data_content)
        manage_duplicate_file_content(
            source=source,
            hash_content=hash_content,
            instance=gdacs_instance,
            response_data=resp_data_content,
            file_name=file_name,
        )
    return gdacs_instance


@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def fetch_event_data(self, parent_id, event_id: int, hazard_type: str, **kwargs):
    # url = f"https://www.gdacs.org/report.aspx?eventid={event_id}&eventtype={hazard_type}"
    url = f"https://www.gdacs.org/gdacsapi/api/events/geteventdata?eventtype={hazard_type}&eventid={event_id}"

    # instance_id is passed in this func in kwargs during retry from self.retry() method.
    # It forbids creating new extraction object during retry.
    instance_id = kwargs.get("instance_id", None)
    hazard_type = ExtractionData.objects.get(id=parent_id).hazard_type
    if not instance_id:
        gdacs_instance = ExtractionData.objects.create(
            source=ExtractionData.Source.GDACS,
            status=ExtractionData.Status.PENDING,
            source_validation_status=ExtractionData.ValidationStatus.NO_VALIDATION,
            attempt_no=0,
            resp_code=0,
            hazard_type=hazard_type,
        )
    else:
        gdacs_instance = ExtractionData.objects.get(id=instance_id)

    # Extract the data from api.
    gdacs_extraction = Extraction(url=url)
    response = None
    try:
        response = gdacs_extraction.pull_data(
            source=ExtractionData.Source.GDACS,
            ext_object_id=gdacs_instance.id,
            retry_count=0,
        )
    except Exception as exc:
        self.retry(exc=exc, kwargs={"instance_id": gdacs_instance.id, "retry_count": self.request.retries})

    # Save the extracted data into the existing gdacs object
    if response:
        gdacs_instance = store_extraction_data(
            response=response,
            source=ExtractionData.Source.GDACS,
            validate_source_func=validate_event_data,
            instance_id=gdacs_instance.id,
            parent_id=parent_id,
            requires_hazard_type=False,
            hazard_type=hazard_type,
        )
        with open(gdacs_instance.resp_data.path, "r") as file:
            data = file.read()

        return {"extraction_id": gdacs_instance.id, "extracted_data": data}


@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def scrape_population_exposure_data(self, parent_id, event_id: int, hazard_type: str, parent_transform_id: str, **kwargs):
    url = f"https://www.gdacs.org/report.aspx?eventid={event_id}&eventtype={hazard_type}"

    # instance_id is passed in this func in kwargs during retry from self.retry() method.
    # It forbids creating new extraction object during retry.
    instance_id = kwargs.get("instance_id", None)
    hazard_type = ExtractionData.objects.get(id=parent_id).hazard_type
    if not instance_id:
        gdacs_instance = ExtractionData.objects.create(
            source=ExtractionData.Source.GDACS,
            status=ExtractionData.Status.PENDING,
            source_validation_status=ExtractionData.ValidationStatus.NO_VALIDATION,
            attempt_no=0,
            resp_code=0,
            hazard_type=hazard_type,
        )
    else:
        gdacs_instance = ExtractionData.objects.get(id=instance_id)

    # Extract the data from api.
    gdacs_extraction = Extraction(url=url)
    response = None
    try:
        response = gdacs_extraction.pull_data(
            source=ExtractionData.Source.GDACS,
            ext_object_id=gdacs_instance.id,
            retry_count=0,
        )
    except Exception as exc:
        self.retry(exc=exc, kwargs={"instance_id": gdacs_instance.id, "retry_count": self.request.retries})

    # Save the extracted data into the existing gdacs object
    if response:
        gdacs_instance = store_extraction_data(
            source=ExtractionData.Source.GDACS,
            response=response,
            validate_source_func=validate_population_exposure,
            instance_id=gdacs_instance.id,
            parent_id=parent_id,
            requires_hazard_type=True,
            hazard_type=hazard_type,
        )


@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def fetch_gdacs_geometry_data(self, parent_id, footprint_url, **kwargs):

    # instance_id is passed in this func in kwargs during retry from self.retry() method.
    # It forbids creating new extraction object during retry.
    instance_id = kwargs.get("instance_id", None)
    hazard_type = ExtractionData.objects.get(id=parent_id).hazard_type
    if not instance_id:
        gdacs_instance = ExtractionData.objects.create(
            source=ExtractionData.Source.GDACS,
            status=ExtractionData.Status.PENDING,
            source_validation_status=ExtractionData.ValidationStatus.NO_VALIDATION,
            attempt_no=0,
            resp_code=0,
            hazard_type=hazard_type,
        )
    else:
        gdacs_instance = ExtractionData.objects.get(id=instance_id)

    gdacs_extraction = Extraction(url=footprint_url)
    response = None
    try:
        response = gdacs_extraction.pull_data(
            source=ExtractionData.Source.GDACS,
            ext_object_id=gdacs_instance.id,
            retry_count=0,
        )
    except Exception as exc:
        self.retry(exc=exc, kwargs={"instance_id": gdacs_instance.id, "retry_count": self.request.retries})

    if response:
        gdacs_instance = store_extraction_data(
            source=ExtractionData.Source.GDACS,
            response=response,
            validate_source_func=validate_gdacs_geometry_data,
            instance_id=gdacs_instance.id,
            parent_id=parent_id,
        )

        with open(gdacs_instance.resp_data.path, "r") as file:
            data = file.read()

        return {"extraction_id": gdacs_instance.id, "extracted_data": data}


@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def import_hazard_data(self, hazard_type: str, hazard_type_str: str, **kwargs):
    """
    Import hazard data from gdacs api
    """
    logger.info(f"Importing {hazard_type} data")

    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    gdacs_url = f"https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH?eventlist={hazard_type}&fromDate={yesterday}&toDate={today}&alertlevel=Green;Orange;Red"  # noqa: E501

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
                geo_result = geo_workflow.apply_async()

                impact_workflow = chain(
                    fetch_event_data.s(
                        parent_id=gdacs_instance.id,
                        event_id=event_id,
                        hazard_type=hazard_type,
                    ),
                    transform_impact_data.s(),
                )
                impact_result = impact_workflow.apply_async()

                load_data.s(event_result.id, geo_result.id, impact_result.id).apply_async()

        logger.info(f"{hazard_type} data imported sucessfully")
