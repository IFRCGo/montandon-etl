import datetime
import hashlib
import json
import logging
import typing
from enum import Enum
from typing import Any, Callable

import pydantic
import requests

from apps.etl.extraction.sources.base.handler import BaseExtraction, BaseExtractionV2
from apps.etl.extraction.sources.base.utils import manage_duplicate_file_content
from apps.etl.models import ExtractionData
from apps.etl.transform.sources.ifrc_event import IFRCEventTransformHandler
from main.celery import app
from main.configs import etl_config
from main.logging import log_extra
from utils.celery import RetryableTask

logger = logging.getLogger(__name__)


class IfrcEventExtractionInputMetadata(pydantic.BaseModel):
    disaster_start_date__gte: typing.Union[datetime.date, str, None]
    limit: int
    offset: int
    ordering: str
    format: typing.Literal["json"]


class IFRCExtractionMetadataType(str, Enum):
    QUERY = "QUERY"


class IFRCExtractionMetadata(pydantic.BaseModel):
    url: str
    type: IFRCExtractionMetadataType


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
    def store_extraction_data(  # type: ignore[reportIncompatibleMethodOverride]
        cls,
        validate_source_func: Callable[[Any], None] | None,
        source: int,
        response: list[Any],
        instance_id: int | None = None,
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
    def handle_extraction(cls, metadata: IfrcEventExtractionInputMetadata) -> int:  # type: ignore[reportIncompatibleMethodOverride]
        """
        Process data extraction.
        Returns:
            int: ID of the extraction instance
        """
        logger.info("Starting data extraction")

        url = f"{etl_config.IFRC_DATA_URL}/api/v2/event/?appeal_type=0,1"
        source = ExtractionData.Source.DREF
        headers = {"accept": "application/json"}

        instance = cls._create_extraction_instance(
            url=url,
            source=source,
            metadata={
                "input": metadata.model_dump(),
            },
        )

        all_data = []
        try:
            cls._update_instance_status(instance, ExtractionData.Status.IN_PROGRESS)

            while True:
                # FIXME: Create multiple extraction items?
                response = requests.get(url, params=metadata.model_dump(), headers=headers, timeout=30)
                response.raise_for_status()
                instance.resp_code = response.status_code
                data_json = response.json()
                all_data.extend(data_json.get("results", []))
                # Check if there's a next page
                if not data_json.get("next"):
                    break
                # Update offset for next request
                metadata.offset += metadata.limit

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
                "Extraction failed",
                exc_info=True,
                extra=log_extra({"source": instance.source}),
            )
            raise


class IFRCEventExtractionV2(BaseExtractionV2[IFRCExtractionMetadata]):
    """
    Handles data extraction from the IFRCEvent API.

    """

    source_enum = ExtractionData.Source.DREF
    extraction_metadata_class = IFRCExtractionMetadata

    def handle_type_query(self):
        url = self.extraction_metadata.url
        self._extraction_fetch_url(
            url,
            headers={"Content-Type": "application/json"},
        )
        response_data = json.loads(self.extraction_object.resp_data.read())
        IFRCEventTransformHandler.task.delay(self.extraction_object.id)
        next_url = response_data.get("next")
        if next_url:
            self.init_extraction(
                metadata=IFRCExtractionMetadata(
                    url=next_url,
                    type=IFRCExtractionMetadataType.QUERY,
                ),
            )

    def handle_extract(self):
        handler_type = self.extraction_metadata.type
        logger.info(f"Starting extraction<{self.extraction_object.pk}> with metadata: {self.extraction_metadata}")
        match handler_type:
            case IFRCExtractionMetadataType.QUERY:
                return self.handle_type_query()
            case _:
                typing.assert_never(handler_type)

    @staticmethod
    @app.task(
        bind=True,
        base=RetryableTask,
    )
    def task(celery_task, extraction_id):
        IFRCEventExtractionV2(celery_task, extraction_id).handle()
