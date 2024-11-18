import uuid

from django.core.management.base import BaseCommand

from apps.etl.extract import Extraction
from apps.etl.models import ExtractionData, ExtractionLog


class Command(BaseCommand):
    help = "Import data from gdacs api"

    def handle(self, *args, **options):
        print("Importing data from GDACS api")

        gdacs_global_url = "https://go-risk.northeurope.cloudapp.azure.com/api/v1/gdacs/?limit=9999"
        gdacs_extraction = Extraction(url=gdacs_global_url)
        response = gdacs_extraction.pull_data(source=ExtractionLog.Source.GDACS)
        raw_data = response.pop("raw_data")
        if response["response_code"] == 200:
            log = ExtractionLog.objects.create(
                **response,
                uuid=uuid.uuid4(),
            )

            ExtractionData.objects.create(
                raw_data=raw_data, extraction_log=log, uuid=log.uuid, response_data_type=ExtractionData.ResponseDataType.JSON
            )
        print("Data Fetched Successfully")
