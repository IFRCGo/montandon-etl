import hashlib
import json
import logging
from typing import Any, Callable

import requests

from apps.etl.extraction.sources.base.handler import BaseExtraction
from apps.etl.extraction.sources.base.utils import manage_duplicate_file_content
from apps.etl.models import ExtractionData
from main.celery import app
from main.logging import log_extra

logger = logging.getLogger(__name__)


HEADERS = {"accept": "application/json"}


class IFRCEventExtraction(BaseExtraction):
    """
    Handles data extraction from the IFRCEvent API.
    """

    @classmethod
    def hash_file_content(cls, content):
        """
        Compute the hash of a file using the specified algorithm.
        :return: Hexadecimal hash of the file
        """
        content = json.dumps(content, sort_keys=True)
        content = content.encode("utf-8")
        return hashlib.sha256(content).hexdigest()

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
        resp_data = response

        # save the additional response data after the data is fetched from api.
        extraction_instance = ExtractionData.objects.get(id=instance_id)
        extraction_instance.resp_data_type = "application/json"
        extraction_instance.save(update_fields=["resp_data_type"])

        # Validate the non empty response data.
        if resp_data:
            # Source validation
            if validate_source_func:
                extraction_instance.source_validation_status = validate_source_func(resp_data)["status"]
                extraction_instance.content_validation = validate_source_func(resp_data)["validation_error"]

            # manage duplicate file content.
            hash_content = cls.hash_file_content(resp_data)
            manage_duplicate_file_content(
                source=extraction_instance.source,
                hash_content=hash_content,
                instance=extraction_instance,
                response_data=resp_data,
                file_name=file_name,
            )
        return resp_data

    @classmethod
    def handle_extraction(cls, url: str, params: dict, headers: dict, source: int) -> dict:
        """
        Process data extraction.
        Returns:
            int: ID of the extraction instance
        """
        logger.info("Starting data extraction")

        instance = cls._create_extraction_instance(url=url, source=source)

        all_data = []
        try:
            cls._update_instance_status(instance, ExtractionData.Status.IN_PROGRESS)

            while True:
                response = requests.get(url, params=params, headers=headers, timeout=30)
                response.raise_for_status()
                instance.resp_code = response.status_code
                data_json = response.json()
                all_data.extend(data_json.get("results", []))
                # Check if there's a next page
                if not data_json.get("next"):
                    break
                # Update offset for next request
                params["offset"] += params["limit"]

            if response.status_code == 200 or response.status_code == 204:
                response_data = cls.store_extraction_data(
                    instance_id=instance.id, source=ExtractionData.Source.DREF, response=all_data, validate_source_func=None
                )
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
    def task(DATA_URL, PARAMS):
        return IFRCEventExtraction().handle_extraction(DATA_URL, PARAMS, HEADERS, ExtractionData.Source.DREF)
