import logging
from typing import Any, Callable

import pydantic
import requests

from apps.etl.extraction.sources.base.handler import BaseExtraction
from apps.etl.extraction.sources.base.utils import manage_duplicate_file_content
from apps.etl.models import ExtractionData
from main.celery import app
from main.configs import etl_config

logger = logging.getLogger(__name__)


class DesInventarExtractionInputMetadata(pydantic.BaseModel):
    country_code: str
    iso3: str


class DesinventarExtraction(BaseExtraction):
    """
    Handles data extraction from the Desinventar API.
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
        Save extracted data into database.
        """
        file_name = f"{source}.zip"
        resp_data = response

        # save the additional response data after the data is fetched from api.
        extraction_instance = ExtractionData.objects.get(id=instance_id)
        # extraction_instance.resp_data_type = "application/zip"
        # FIXME(tnagorra): the eoAPI server does not support zip so using octet-stream for the time being
        extraction_instance.resp_data_type = "application/octet-stream"
        extraction_instance.save(update_fields=["resp_data_type"])

        # Validate the non empty response data.
        if resp_data:
            # manage duplicate file content.
            manage_duplicate_file_content(
                source=extraction_instance.source,
                # FIXME(tnagorra): We need to calculate hash for zip file
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
    def task(metadata: dict):  # type: ignore[reportIncompatibleMethodOverride]
        input_metadata = DesInventarExtractionInputMetadata(**metadata)
        url = f"{etl_config.DESINVENTAR_DATA_URL}/DesInventar/download/DI_export_{input_metadata.country_code}.zip"
        return DesinventarExtraction().handle_extraction(
            url=url,
            params=input_metadata.model_dump(),
            headers=None,
            source=ExtractionData.Source.DESINVENTAR.value,
            parent_id=None,
            timeout=180,
        )
