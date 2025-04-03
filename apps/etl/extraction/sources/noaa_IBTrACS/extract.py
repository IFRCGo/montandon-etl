import logging
from typing import Any, Callable

import requests

from apps.etl.extraction.sources.base.handler import BaseExtraction
from apps.etl.extraction.sources.base.utils import manage_duplicate_file_content
from apps.etl.models import ExtractionData
from main.celery import app

logger = logging.getLogger(__name__)


class IBTrACSExtraction(BaseExtraction):
    """
    Handles data extraction of IBTrACS
    """

    @classmethod
    def store_extraction_data(  # type: ignore[reportIncompatibleMethodOverride]
        cls,
        validate_source_func: Callable[[Any], None] | None,
        source: int,
        response: requests.Response,
        instance_id: int | None = None,
    ):
        """
        Save extracted data into database. Checks for duplicate content using hashing.
        """
        file_name = f"{source}.csv"
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
    def _save_response_data(cls, instance: ExtractionData, response: requests.Response) -> dict:
        instance = cls.store_extraction_data(
            response=response,
            source=ExtractionData.Source.DESINVENTAR,
            validate_source_func=None,
            instance_id=instance.id,
        )
        return response

    @staticmethod
    @app.task
    def task(url: str):  # type: ignore[reportIncompatibleMethodOverride]
        return IBTrACSExtraction().handle_extraction(
            url=url,
            headers=None,
            params=None,
            source=ExtractionData.Source.IBTRACS,
        )
