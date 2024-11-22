import logging
import typing
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from apps.etl.extract import Extraction
from apps.etl.models import ExtractionData, HazardType

logger = logging.getLogger(__name__)


def logging_context(context) -> dict:
    return {
        "context": context,
    }


def get_as_int(value: typing.Optional[str]) -> typing.Optional[int]:
    if value is None:
        return
    if value == "-":
        return
    return int(value)


class Command(BaseCommand):
    help = "Import data from gdacs api"

    def scrape_population_exposure_data(self, parent_gdacs_instance, event_id: int, hazard_type_str: str):
        url = f"https://www.gdacs.org/report.aspx?eventid={event_id}&eventtype={hazard_type_str}"
        population_exposure = {}
        try:

            tables = pd.read_html(url)
            displacement_data_raw = tables[0].replace({np.nan: None}).to_dict()
            displacement_data = dict(
                zip(
                    displacement_data_raw[0].values(),  # First column are keys
                    displacement_data_raw[1].values(),  # Second column are values
                )
            )

            if hazard_type_str == "EQ":
                population_exposure["exposed_population"] = displacement_data.get("Exposed Population:")

            elif hazard_type_str == "TC":
                population_exposure["exposed_population"] = displacement_data.get("Exposed population")

            elif hazard_type_str == "FL":
                population_exposure["death"] = get_as_int(displacement_data.get("Death:"))
                population_exposure["displaced"] = get_as_int(displacement_data.get("Displaced:"))

            elif hazard_type_str == "DR":
                population_exposure["impact"] = displacement_data.get("Impact:")

            elif hazard_type_str == "WF":
                population_exposure["people_affected"] = displacement_data.get("People affected:")

        except Exception:
            logger.error(
                "Error scraping data",
                extra=logging_context(dict(url=url)),
                exc_info=True,
            )

            pop_exposure_data = ExtractionData.objects.create(
                parent=parent_gdacs_instance,
                source=ExtractionData.Source.GDACS,
                url=url,
                status=ExtractionData.Status.FAILED,
                resp_data_type="text/html",
                attempt_no=1,  # TODO need to set a function for automatically set attempt_no
                resp_code=201,  # TODO need to set dynamically
                source_validation_status=2,
            )
            return

        pop_exposure_data = ExtractionData.objects.create(
            parent=parent_gdacs_instance,
            source=ExtractionData.Source.GDACS,
            url=url,
            status=ExtractionData.Status.SUCCESS,
            resp_data_type="text/html",
            attempt_no=1,  # TODO need to set a function for automatically set attempt_no
            resp_code=200,  # TODO need to set dynamically
            source_validation_status=1,
        )
        file_name = "gdacs_pop_exposure.html"
        resp_data_content = population_exposure
        pop_exposure_data.resp_data.save(file_name, ContentFile(resp_data_content))

    def import_hazard_data(self, hazard_type, hazard_type_str):
        print(f"Importing {hazard_type} data")
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)

        gdacs_url = f"https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH?eventlist={hazard_type}&fromDate={yesterday}&toDate={today}&alertlevel=Green;Orange;Red"  # noqa: E501
        gdacs_extraction = Extraction(url=gdacs_url)
        response = gdacs_extraction.pull_data(source=ExtractionData.Source.GDACS)

        resp_data = response.pop("resp_data")
        resp_data_content = resp_data.content
        file_extension = response.pop("file_extension")
        file_name = f"gdacs.{file_extension}"

        gdacs_instance = ExtractionData(
            **response,
        )
        gdacs_instance.resp_data.save(file_name, ContentFile(resp_data_content))

        for old_data in resp_data.json()["features"]:
            event_id = old_data["properties"]["eventid"]
            episode_id = old_data["properties"]["episodeid"]

            self.scrape_population_exposure_data(gdacs_instance, event_id, hazard_type_str)

            footprint_url = old_data["properties"]["url"]["geometry"]
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

        print(f"{hazard_type} data imported sucessfully")

    def handle(self, *args, **options):
        print("Importing data from GDACS api")
        self.import_hazard_data("EQ", HazardType.EARTHQUAKE)
        self.import_hazard_data("TC", HazardType.CYCLONE)
        self.import_hazard_data("FL", HazardType.FLOOD)
        self.import_hazard_data("DR", HazardType.DROUGHT)
        self.import_hazard_data("WF", HazardType.WILDFIRE)
        print("Data Imported Sucessfully")
