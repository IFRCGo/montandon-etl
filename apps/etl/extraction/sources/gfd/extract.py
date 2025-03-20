import base64
import hashlib
import json
import logging
import tempfile
from typing import Any, Callable

import ee
import requests
from django.conf import settings

from apps.etl.extraction.sources.base.handler import BaseExtraction
from apps.etl.extraction.sources.base.utils import manage_duplicate_file_content
from apps.etl.models import ExtractionData
from main.celery import app
from main.logging import log_extra

logger = logging.getLogger(__name__)


DATA_URL = "https://earthengine.googleapis.com/v1alpha/projects/earthengine-legacy/assets/GLOBAL_FLOOD_DB/MODIS_EVENTS/V1"


class GFDExtraction(BaseExtraction):
    @classmethod
    def decode_json(cls, encoded_str):
        """Decodes a Base64 string back to a JSON object."""
        decoded_data = base64.urlsafe_b64decode(encoded_str.encode()).decode()
        return json.loads(decoded_data)

    @classmethod
    def get_json_credentials(cls, content):
        with tempfile.NamedTemporaryFile(delete=False, mode="w") as temp_file:
            json_string = json.dumps(content, sort_keys=True)
            temp_file.write(json_string)
            temp_path = temp_file.name
        return temp_path

    @classmethod
    def hash_json_content(cls, json_data):
        """Hashes a JSON object using SHA256."""
        json_string = json.dumps(json_data, sort_keys=True)
        return hashlib.sha256(json_string.encode()).hexdigest()

    @classmethod
    def store_extraction_data(
        cls,
        validate_source_func: Callable[[Any], None],
        source: int,
        response: dict,
        instance_id: int = None,
    ):
        """
        Save extracted data into database. Checks for duplicate content using hashing.
        """
        file_extension = "json"
        file_name = f"{source}.{file_extension}"
        resp_data_content = json.dumps(response)

        # save the additional response data after the data is fetched from api.
        extraction_instance = ExtractionData.objects.get(id=instance_id)
        extraction_instance.resp_data_type = "application/json"
        extraction_instance.save(update_fields=["resp_data_type"])

        # Validate the non empty response data.
        if resp_data_content:
            # Source validation
            if validate_source_func:
                extraction_instance.source_validation_status = validate_source_func(resp_data_content)["status"]
                extraction_instance.content_validation = validate_source_func(resp_data_content)["validation_error"]

            # manage duplicate file content.
            hash_content = cls.hash_json_content(resp_data_content)
            manage_duplicate_file_content(
                source=extraction_instance.source,
                hash_content=hash_content,
                instance=extraction_instance,
                response_data=resp_data_content,
                file_name=file_name,
            )
        return extraction_instance

    @classmethod
    def _save_response_data(cls, instance: ExtractionData, response: requests.Response) -> dict:
        """
        Save the response data to the extraction instance.
        Args:
            instance: ExtractionData instance to save to
            response: Response object containing the data
        Returns:
            dict: Parsed JSON response content
        """
        instance = cls.store_extraction_data(
            response=response,
            source=instance.source,
            validate_source_func=None,
            instance_id=instance.id,
        )

        return response

    @classmethod
    def get_flood_data(cls, collection, batch_size=1000):
        """Retrieve flood metadata in batches to avoid memory issues."""
        total_size = collection.size().getInfo()

        all_data = []
        for i in range(0, total_size, batch_size):
            batch = collection.toList(batch_size, i).getInfo()
            all_data.extend([feature for feature in batch])

        return all_data

    @classmethod
    def handle_extraction(cls, url: str, source: int, start_date, end_date) -> int:
        """
        Process data extraction.
        Returns:
            int: ID of the extraction instance
        """
        logger.info("Starting data extraction")
        instance = cls._create_extraction_instance(url=url, source=source)

        try:
            cls._update_instance_status(instance, ExtractionData.Status.IN_PROGRESS)
            response = cls.extract_data(start_date, end_date)
            response_data = cls._save_response_data(instance, response)
            # Check if response contains data
            if response_data:
                cls._update_instance_status(instance, ExtractionData.Status.SUCCESS)
                logger.info("Data extracted successfully")
            else:
                cls._update_instance_status(
                    instance,
                    ExtractionData.Status.SUCCESS,
                    ExtractionData.ValidationStatus.NO_DATA,
                    update_validation=True,
                )
                logger.warning("No hazard data found in response")

            return instance.id

        except requests.exceptions.RequestException:
            cls._update_instance_status(instance, ExtractionData.Status.FAILED)
            logger.error(
                "extraction failed",
                exc_info=True,
                extra=log_extra(
                    {
                        "source": instance.source,
                    }
                ),
            )
            raise

    @classmethod
    def extract_data(cls, start_date=None, end_date=None):
        # Set up authentication
        service_account = settings.GFD_SERVICE_ACCOUNT

        # # Decode the earthengine credential
        decoded_json = cls.decode_json(settings.GFD_CREDENTIAL)
        credential_file_path = cls.get_json_credentials(decoded_json)

        # Authenticate
        credentials = ee.ServiceAccountCredentials(service_account, credential_file_path)
        ee.Initialize(credentials)

        # Load Global Flood Database (GFD)
        gfd_data = ee.ImageCollection("GLOBAL_FLOOD_DB/MODIS_EVENTS/V1")

        # Filter flood events by date
        if start_date and end_date:
            gfd_data = gfd_data.filterDate(str(start_date), str(end_date))

        flood_data = cls.get_flood_data(gfd_data, batch_size=500)
        return flood_data

    @staticmethod
    @app.task
    def task(start_date=None, end_date=None):
        return GFDExtraction().handle_extraction(DATA_URL, ExtractionData.Source.GFD, start_date, end_date)
