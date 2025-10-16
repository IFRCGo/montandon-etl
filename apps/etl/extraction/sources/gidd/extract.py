import logging
import typing
from enum import Enum

import pydantic

from apps.etl.extraction.sources.base.handler import BaseExtractionV2
from apps.etl.models import ExtractionData
from apps.etl.transform.sources.gidd import GIDDTransformHandler
from main.celery import CeleryQueue, app
from main.configs import etl_config
from main.logging import log_extra
from utils.celery import RetryableTask

logger = logging.getLogger(__name__)


class GIDDExtractionMetadataType(str, Enum):
    QUERY = "QUERY"


class GIDDExtractionMetadata(pydantic.BaseModel):
    url: str
    type: GIDDExtractionMetadataType


class GIDDExtraction(BaseExtractionV2[GIDDExtractionMetadata]):
    """
    Handles data extraction from the GIDD API.
    """

    source_enum = ExtractionData.Source.GIDD
    extraction_metadata_class = GIDDExtractionMetadata

    def _handle_type_query(self):
        url = self.extraction_metadata.url
        headers = {"Content-Type": "application/json"}
        params = {"client_id": etl_config.IDMC_CLIENT_ID}
        extraction_status = self._extraction_fetch_url(url, headers=headers, params=params)
        if not extraction_status:
            logger.warning(
                "Failed to extract data",
                extra=log_extra({"source": self.source_enum, "extraction": self.extraction_object}),
            )
            return

        GIDDTransformHandler.task.delay(self.extraction_object.id)

    def handle_extract(self, retrigger: bool):
        handler_type = self.extraction_metadata.type
        logger.info(f"Starting extraction<{self.extraction_object.pk}> with metadata: {self.extraction_metadata}")
        match handler_type:
            case GIDDExtractionMetadataType.QUERY:
                return self._handle_type_query()
            case _:
                typing.assert_never(handler_type)

    @staticmethod
    @app.task(bind=True, base=RetryableTask, queue=CeleryQueue.EXTRACTION)
    def task(celery_task, extraction_id):  # type: ignore[reportIncompatibleMethodOverride]
        GIDDExtraction(celery_task, extraction_id).handle()
