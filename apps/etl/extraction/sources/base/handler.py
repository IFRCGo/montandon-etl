import json
import logging
import uuid
from typing import Any, Callable

import requests

from apps.etl.extraction.sources.base.utils import (
    hash_file_content,
    manage_duplicate_file_content,
)
from apps.etl.models import ExtractionData
from main.celery import app
from main.logging import log_extra

logger = logging.getLogger(__name__)


class BaseExtraction:
    """
    Handles data extraction.
    """

    @classmethod
    def store_extraction_data(
        cls,
        validate_source_func: Callable[[Any], None],
        source: int,
        response: dict,
        instance_id: int | None = None,
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
        if resp_data_content:
            # Source validation
            if validate_source_func:
                extraction_instance.source_validation_status = validate_source_func(resp_data_content)["status"]
                extraction_instance.content_validation = validate_source_func(resp_data_content)["validation_error"]

            # manage duplicate file content.
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
    def _create_extraction_instance(
        cls,
        url: str,
        source: int,
        parent_id: int = None,
        status=ExtractionData.Status.PENDING,
        hazard_type=None,
        metadata={},
    ) -> ExtractionData:
        """
        Create and return a new extraction instance with initial status.
        Returns:
            ExtractionData: The created extraction instance
        """
        parent = ExtractionData.objects.filter(id=parent_id).first()
        return ExtractionData.objects.create(
            source=source,
            url=url,
            status=status,
            source_validation_status=ExtractionData.ValidationStatus.NO_VALIDATION,
            trace_id=parent.trace_id if parent else uuid.uuid4(),
            hazard_type=hazard_type,
            attempt_no=0,
            resp_code=0,
            parent_id=parent_id,
            metadata=metadata,
        )

    @classmethod
    def _update_instance_status(
        cls, instance: ExtractionData, status: int, validation_status: int | None = None, update_validation: bool = False
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

        return json.loads(response.content)

    @classmethod
    def handle_extraction(
        cls, url: str, params: dict | None, headers: dict, source: int, parent_id: int | None = None
    ) -> dict:
        """
        Process data extraction.
        Returns:
            int: ID of the extraction instance
        """
        logger.info("Starting data extraction")
        instance = cls._create_extraction_instance(url=url, source=source, parent_id=parent_id)

        try:
            cls._update_instance_status(instance, ExtractionData.Status.IN_PROGRESS)

            response = requests.get(url, params=params, headers=headers, timeout=30)
            response.raise_for_status()
            instance.resp_code = response.status_code
            instance.save(update_fields=["resp_code"])

            if response.status_code == 200:
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

    @staticmethod
    @app.task
    def task():
        """
        Not NotImplemented due to celery limitation with classmethod
        Eg: return XYZExtraction.handle_extraction(url, source)
        """
        raise NotImplementedError()
