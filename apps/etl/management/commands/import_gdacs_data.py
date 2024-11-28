import hashlib
import json
import logging
from datetime import datetime, timedelta

import requests
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from pydantic import ValidationError

from apps.etl.extract import Extraction
from apps.etl.extraction_validators.gdacs_events_validator import (
    GdacsEventsDataValidator,
)
from apps.etl.models import ExtractionData, HazardType

logger = logging.getLogger(__name__)


def hash_file(file):
    """
    Compute the hash of a file using the specified algorithm.
    :return: Hexadecimal hash of the file
    """
    if file:
        if file.closed:
            file.open()

        # Compute the hash of the file's content
        hash_sha256 = hashlib.sha256()  # Use others hashlib if preferred
        for chunk in file.chunks():  # Read file in chunks to avoid memory issues
            hash_sha256.update(chunk)

        file_hash = hash_sha256.hexdigest()
        file.close()

        return file_hash


class Command(BaseCommand):
    help = "Import data from gdacs api"

    def scrape_population_exposure_data(self, parent_gdacs_instance, event_id: int, hazard_type_str: str):
        url = f"https://www.gdacs.org/report.aspx?eventid={event_id}&eventtype={hazard_type_str}"

        response = requests.get(url)
        if response.status_code == 200:
            html_content = response.text
            pop_exposure_data = ExtractionData(
                parent=parent_gdacs_instance,
                source=ExtractionData.Source.GDACS,
                url=url,
                status=ExtractionData.Status.SUCCESS,
                resp_data_type=response.headers.get("Content-Type", ""),
                attempt_no=1,  # TODO need to set a function for automatically set attempt_no
                resp_code=response.status_code,
                source_validation_status=ExtractionData.ValidationStatus.SUCCESS,
            )
            file_name = "gdacs_pop_exposure.html"
            pop_exposure_data.resp_data.save(file_name, ContentFile(html_content))

            return

        ExtractionData.objects.create(
            parent=parent_gdacs_instance,
            source=ExtractionData.Source.GDACS,
            url=url,
            status=ExtractionData.Status.FAILED,
            resp_data_type=response.headers.get("Content-Type", ""),
            attempt_no=1,  # TODO need to set a function for automatically set attempt_no
            resp_code=response.status_code,
            source_validation_status=ExtractionData.ValidationStatus.FAILED,
        )

    def import_hazard_data(self, hazard_type, hazard_type_str):
        print(f"Importing {hazard_type} data")
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)

        gdacs_url = f"https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH?eventlist={hazard_type}&fromDate={yesterday}&toDate={today}&alertlevel=Green;Orange;Red"  # noqa: E501
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

            # Validate the response data, if changes encountered then save the erroe response
            try:
                resp_data_for_validation = json.loads(resp_data_content.decode("utf-8"))
                GdacsEventsDataValidator(**resp_data_for_validation)
                validation_error = ""
            except ValidationError as e:
                validation_error = e.json()
            gdacs_instance.source_validation_status = (
                ExtractionData.ValidationStatus.FAILED if validation_error else ExtractionData.ValidationStatus.SUCCESS
            )
            gdacs_instance.content_validation = validation_error if validation_error else ""
            gdacs_instance.resp_data.save(file_name, ContentFile(resp_data_content))
            # save hash value for file
            gdacs_instance.file_hash = hash_file(gdacs_instance.resp_data)

            for feature in resp_data.json()["features"]:
                event_id = feature["properties"]["eventid"]
                episode_id = feature["properties"]["episodeid"]

                self.scrape_population_exposure_data(gdacs_instance, event_id, hazard_type_str)

                footprint_url = feature["properties"]["url"]["geometry"]
                if hazard_type == HazardType.CYCLONE:
                    footprint_url = f"https://www.gdacs.org/contentdata/resources/{hazard_type_str}/{event_id}/geojson_{event_id}_{episode_id}.geojson"  # noqa: E501
                    gdacs_extraction_footprint = Extraction(url=footprint_url)
                    response = gdacs_extraction_footprint.pull_data(source=ExtractionData.Source.GDACS)
                    resp_data = response.pop("resp_data")
                    resp_data_content = resp_data.content
                    file_extension = response.pop("file_extension")
                    file_name = f"gdacs_footprint.{file_extension}"
                    gdacs_instance = ExtractionData(**response, parent=gdacs_instance)
                    gdacs_instance.resp_data.save(file_name, ContentFile(resp_data_content))

        gdacs_instance.save()

        print(f"{hazard_type} data imported sucessfully")

    def handle(self, *args, **options):
        print("Importing data from GDACS api")
        self.import_hazard_data("EQ", HazardType.EARTHQUAKE)
        self.import_hazard_data("TC", HazardType.CYCLONE)
        self.import_hazard_data("FL", HazardType.FLOOD)
        self.import_hazard_data("DR", HazardType.DROUGHT)
        self.import_hazard_data("WF", HazardType.WILDFIRE)
        print("Data Imported Sucessfully")
