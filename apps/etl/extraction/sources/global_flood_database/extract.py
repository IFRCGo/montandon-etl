import json
import logging
import requests
from typing import Any, Callable
from datetime import datetime, timedelta
from django.conf import settings

from apps.etl.extraction.sources.base.utils import (
    hash_file_content,
    manage_duplicate_file_content,
)
from apps.etl.models import ExtractionData
from main.celery import app

logger = logging.getLogger(__name__)

import ee
import os

DATA_URL = "https://earthengine.googleapis.com/v1alpha/projects/earthengine-legacy/assets/GLOBAL_FLOOD_DB/MODIS_EVENTS/V1"

class GFDExtraction(BaseExtraction):


    @classmethod
    def store_extraction_data(
        cls,
        validate_source_func: Callable[[Any], None],
        source: int,
        response: dict,
        instance_id: int = None,
    ):
        """
        Save extracted data into data base. Checks for duplicate conent using hashing.
        """
        file_extension = "json"
        file_name = f"{source}.{file_extension}"
        resp_data_content = response

        # save the additional response data after the data is fetched from api.
        extraction_instance = ExtractionData.objects.get(id=instance_id)
        extraction_instance.resp_data_type = "application/json"
        extraction_instance.save()

        # Validate the non empty response data.
        if resp_data_content:
            # Source validation
            if validate_source_func:
                extraction_instance.source_validation_status = validate_source_func(resp_data_content)["status"]
                extraction_instance.content_validation = validate_source_func(resp_data_content)["validation_error"]

            # manage duplicate file content.
            resp_data_content = str(resp_data_content).encode("utf-8")
            hash_content = hash_file_content(resp_data_content)

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
        # print(f"Total flood events: {total_size}")

        all_data = []
        for i in range(0, total_size, batch_size):
            batch = collection.toList(batch_size, i).getInfo()
            all_data.extend([feature for feature in batch])
            # print(f"Fetched {len(all_data)}/{total_size} records")

        return all_data

    @classmethod
    def handle_extraction(cls, url: str, source: int, start_date, end_date) -> int:
        """
        Process data extraction.
        Returns:
            int: ID of the extraction instance
        """
        logger.info("Starting data extraction")
        # print("Starting data extraction")
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

            # print("Data extraction done")
            return instance.id

        except requests.exceptions.RequestException:
            cls._update_instance_status(instance, ExtractionData.Status.FAILED)
            logger.error(
                "extraction failed",
                exc_info=True,
                extra={
                    "source": instance.source,
                },
            )
            raise

    @classmethod
    def extract_data(cls, start_date=None, end_date=None):
        # Set up authentication
        # TODO Remove this autherntication and use official authentication
        service_account = "rup-rajbanshi@gidd-1671534293682.iam.gserviceaccount.com"

        # Get the script's directory
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))

        # Construct the JSON file path
        # TODO Add json key file official
        json_key_path = os.path.join(BASE_DIR, "gidd-1671534293682-dab333fe24ec.json")

        # Authenticate
        credentials = ee.ServiceAccountCredentials(service_account, json_key_path)
        ee.Initialize(credentials)

        # Load Global Flood Database (GFD)
        gfd_data = ee.ImageCollection("GLOBAL_FLOOD_DB/MODIS_EVENTS/V1")

        # Filter flood events by date
        if start_date and end_date:
            gfd_data = gfd_data.filterDate(str(start_date), str(end_date))


        flood_data = cls.get_flood_data(gfd_data, batch_size=500)
        print(f"Extracted {len(flood_data)} flood events.")

        # Check if there are flood events in this time range
        count = gfd_data.size().getInfo()
        print(f"Number of flood events found: {count}")


        return flood_data

    @staticmethod
    @app.task
    def task(start_date=None, end_date=None):
        return GFDExtraction().handle_extraction(
            DATA_URL,
            ExtractionData.Source.GIDD,
            start_date,
            end_date
        )




