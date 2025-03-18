import logging
from typing import Any, Callable

import requests

from apps.etl.extraction.sources.base.handler import BaseExtraction
from apps.etl.extraction.sources.base.utils import manage_duplicate_file_content
from apps.etl.models import ExtractionData
from main.celery import app

logger = logging.getLogger(__name__)


class IBTRACSExtraction(BaseExtraction):
    """
    Handles data extraction of IBTrACS
    """

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
        file_name = f"{source}.zip"
        resp_data = response

        # save the additional response data after the data is fetched from api.
        extraction_instance = ExtractionData.objects.get(id=instance_id)
        extraction_instance.resp_data_type = "application/csv"
        extraction_instance.save(update_fields=["resp_data_type"])

        # Validate the non empty response data.
        if resp_data:
            # manage duplicate file content.
            manage_duplicate_file_content(
                source=extraction_instance.source,
                hash_content=None,
                instance=extraction_instance,
                response_data=resp_data.content,
                file_name=file_name,
            )
        return resp_data.content

    @classmethod
    def handle_extraction(cls, url: str, params: dict, source: int):
        """
        Process data extraction
        Returns:
            csv file
        """
        logger.info("Starting data extraction")
        instance = cls._create_extraction_instance(url=url, source=source)
        try:
            cls._update_instance_status(instance, ExtractionData.Status.IN_PROGRESS)
            response = requests.get(url=url, params=params)
            response.raise_for_status()
            instance.resp_code = response.status_code
            instance.save(update_fields=["resp_code"])

            if response.status_code == 200:
                response_data = cls.store_extraction_data(
                    instance_id=instance.id,
                    source=ExtractionData.Source.IBTRACS,
                    response=response,
                    validate_source_func=None,
                )
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
                    logger.warning("NO hazard data found in response")
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

    @staticmethod
    @app.task
    def task(DATA_URL):
        return IBTRACSExtraction().handle_extraction(url=DATA_URL, params={}, source=ExtractionData.Source.IBTRACS)
