from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from apps.etl.extract import Extraction
from apps.etl.models import ExtractionData


class Command(BaseCommand):
    help = "Import data from gdacs api"

    def handle(self, *args, **options):
        print("Importing data from GDACS api")

        gdacs_global_url = "https://go-risk.northeurope.cloudapp.azure.com/api/v1/gdacs/?limit=9999"
        gdacs_extraction = Extraction(url=gdacs_global_url)
        response = gdacs_extraction.pull_data(source=ExtractionData.Source.GDACS)
        resp_data = response.pop("resp_data")
        file_extension = response.pop("file_extension")
        file_name = f"gdacs.{file_extension}"

        if response["resp_code"] == 200:
            gdacs_instance = ExtractionData(
                **response,
            )

            if isinstance(resp_data, str):
                # Convert text content to ContentFile
                gdacs_instance.resp_data.save(file_name, ContentFile(resp_data))

            # For binary content
            gdacs_instance.resp_data.save(file_name, ContentFile(resp_data))

        print("Data Fetched Successfully")
