import json
import logging
from typing import Any, Callable

import requests
from django.conf import settings

from apps.etl.extraction.sources.base.extract import Extraction
from apps.etl.extraction.sources.base.utils import (
    hash_file_content,
    manage_duplicate_file_content,
)
from apps.etl.models import ExtractionData
from main.celery import app

logger = logging.getLogger(__name__)

HEADERS = {"accept": "application/json"}
PARAMS = {"client_id": settings.IDMC_CLIENT_ID}


class IDUExtraction(Extraction):
    """
    Handles data extraction from the IDU API for hazard data.
    """

    def __init__(self, url: str = None):
        """
        Initialize the IDU extraction process.
        Args:
            url (str, optional): Override the default API URL. Defaults to BASE_URL.
        """
        super().__init__()

    @staticmethod
    def store_extraction_data(
        validate_source_func: Callable[[Any], None],
        response: dict,
        source: ExtractionData.Source = None,
        instance_id: int = None,
    ):
        """
        Save extracted data into data base. Checks for duplicate conent using hashing.
        """
        file_extension = "json"
        file_name = f"{source}.{file_extension}"
        resp_data_content = response.content

        # save the additional response data after the data is fetched from api.
        extraction_instance = ExtractionData.objects.get(id=instance_id)
        extraction_instance.resp_data_type = response.headers.get("Content-Type", "")
        extraction_instance.save()

        # Validate the non empty response data.
        if resp_data_content and not response.status_code == 204:
            # Source validation
            if validate_source_func:
                extraction_instance.source_validation_status = validate_source_func(resp_data_content)["status"]
                extraction_instance.content_validation = validate_source_func(resp_data_content)["validation_error"]

            # manage duplicate file content.
            hash_content = hash_file_content(resp_data_content)
            manage_duplicate_file_content(
                source=source,
                hash_content=hash_content,
                instance=extraction_instance,
                response_data=resp_data_content,
                file_name=file_name,
            )
        return extraction_instance

    @staticmethod
    def _create_extraction_instance(url) -> ExtractionData:
        """
        Create and return a new extraction instance with initial status.
        Returns:
            ExtractionData: The created extraction instance
        """
        return ExtractionData.objects.create(
            source=ExtractionData.Source.IDU,
            url=url,
            status=ExtractionData.Status.PENDING,
            source_validation_status=ExtractionData.ValidationStatus.NO_VALIDATION,
            hazard_type=None,
            attempt_no=0,
            resp_code=0,
        )

    @staticmethod
    def _update_instance_status(
        instance: ExtractionData, status: int, validation_status: int = None, update_validation: bool = False
    ) -> None:
        """
        Update the status of the extraction instance.
        Args:
            instance: ExtractionData instance to update
            status: New status to set
            validation_status: Optional validation status to set
            update_validation: Whether to update validation status
        """
        instance.status = status
        if update_validation and validation_status:
            instance.source_validation_status = validation_status
            instance.save(update_fields=["status", "source_validation_status"])
        else:
            instance.save(update_fields=["status"])

    @staticmethod
    def _save_response_data(instance: ExtractionData, response: requests.Response) -> dict:
        """
        Save the response data to the extraction instance.
        Args:
            instance: ExtractionData instance to save to
            response: Response object containing the data
        Returns:
            dict: Parsed JSON response content
        """
        instance = IDUExtraction.store_extraction_data(
            response=response,
            source=ExtractionData.Source.IDU,
            validate_source_func=None,
            instance_id=instance.id,
        )

        return json.loads(response.content)

    @staticmethod
    @app.task
    def handle_extraction(url) -> dict:
        """
        Process IDU data extraction.
        Returns:
            int: ID of the extraction instance
        """
        logger.info("Starting IDU data extraction")
        print("Starting IDU data extraction")
        instance = IDUExtraction._create_extraction_instance(url=url)

        try:
            IDUExtraction._update_instance_status(instance, ExtractionData.Status.IN_PROGRESS)

            response = requests.get(url, params=PARAMS, headers=HEADERS, timeout=30)
            response.raise_for_status()
            instance.resp_code = response.status_code

            if response.status_code == 200:
                response_data = IDUExtraction._save_response_data(instance, response)
                # Check if response contains data
                if response_data:
                    IDUExtraction._update_instance_status(instance, ExtractionData.Status.SUCCESS)
                    logger.info("IDU data extracted successfully")
                else:
                    IDUExtraction._update_instance_status(
                        instance,
                        ExtractionData.Status.SUCCESS,
                        ExtractionData.ValidationStatus.NO_DATA,
                        update_validation=True,
                    )
                    logger.warning("No hazard data found in IDU response")

            return instance.id

        except requests.exceptions.RequestException:
            IDUExtraction._update_instance_status(instance, ExtractionData.Status.FAILED)
            logger.error(
                "IDU extraction failed",
                exc_info=True,
                extra={
                    "source": ExtractionData.Source.IDU,
                },
            )
            raise
