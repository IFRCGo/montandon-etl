import logging
from datetime import datetime, timedelta

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from apps.etl.extract import Extraction
from apps.etl.models import ExtractionData, HazardType

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Import data from gdacs api"

    def import_hazard_data(self, hazard_type):
        print("Importing data from GDACS api")

        today = datetime.now().date()
        yesterday = today - timedelta(days=1)

        gdacs_url = f"https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH?eventlist={hazard_type}&fromDate={yesterday}&toDate={today}&alertlevel=Green;Orange;Red"  # noqa: E501
        gdacs_extraction = Extraction(url=gdacs_url)
        response = gdacs_extraction.pull_data(source=ExtractionData.Source.GDACS)
        print("RESP", response)

        resp_data = response.pop("resp_data")
        file_extension = response.pop("file_extension")
        file_name = f"gdacs.{file_extension}"

        gdacs_instance = ExtractionData(
            **response,
        )
        gdacs_instance.resp_data.save(file_name, ContentFile(resp_data))

        print("Data Fetched Successfully")

    def handle(self, *args, **options):
        self.import_hazard_data(HazardType.EARTHQUAKE)
        self.import_hazard_data(HazardType.CYCLONE)
        self.import_hazard_data(HazardType.FLOOD)
        self.import_hazard_data(HazardType.DROUGHT)
        self.import_hazard_data(HazardType.WILDFIRE)
