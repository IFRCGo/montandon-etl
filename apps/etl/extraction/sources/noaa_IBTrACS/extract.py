import logging
import typing
from enum import Enum

import pydantic

from apps.etl.extraction.sources.base.handler import BaseExtractionV2
from apps.etl.models import ExtractionData
from apps.etl.transform.sources.noaa_ibtracs import IbtracsTransformHandler
from main.celery import app
from utils.celery import RetryableTask

logger = logging.getLogger(__name__)


class IBTrACSExtractionMetadataType(str, Enum):
    QUERY = "QUERY"


class IBTrACSExtractionMetadata(pydantic.BaseModel):
    url: str
    type: IBTrACSExtractionMetadataType


class IBTrACSExtraction(BaseExtractionV2[IBTrACSExtractionMetadata]):
    """
    Handle IBTrACS data extraction
    """

    source_enum = ExtractionData.Source.IBTRACS
    extraction_metadata_class = IBTrACSExtractionMetadata

    def handle_type_query(self):
        self._extraction_fetch_url(
            self.extraction_metadata.url,
            headers={"Content-Type": "application/json"},
        )
        IbtracsTransformHandler.task.delay(self.extraction_object.id)

    def handle_extract(self):
        handler_type = self.extraction_metadata.type
        logger.info(f"Starting extraction<{self.extraction_object.pk}> with metadata: {self.extraction_metadata}")
        match handler_type:
            case IBTrACSExtractionMetadataType.QUERY:
                return self.handle_type_query()
            case _:
                typing.assert_never(handler_type)

    @staticmethod
    @app.task(
        bind=True,
        base=RetryableTask,
    )
    def task(celery_task, extraction_id):  # type: ignore[reportIncompatibleMethodOverride]
        IBTrACSExtraction(celery_task, extraction_id).handle()
