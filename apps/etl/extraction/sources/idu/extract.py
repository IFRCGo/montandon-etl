import logging
import typing
from enum import Enum

import pydantic

from apps.etl.extraction.sources.base.handler import BaseExtractionV2
from apps.etl.models import ExtractionData
from apps.etl.transform.sources.idu import IDUTransformHandler
from main.celery import CeleryQueue, app
from main.configs import etl_config
from utils.celery import RetryableTask

logger = logging.getLogger(__name__)


class IDUExtractionMetadataType(str, Enum):
    QUERY = "QUERY"


class IDUExtractionMetadata(pydantic.BaseModel):
    url: str
    type: IDUExtractionMetadataType


class IDUExtraction(BaseExtractionV2[IDUExtractionMetadata]):
    """
    Handles data extraction from the IDU API.
    """

    source_enum = ExtractionData.Source.IDU
    extraction_metadata_class = IDUExtractionMetadata

    def _handle_type_query(self):
        url = self.extraction_metadata.url
        headers = {"Content-Type": "application/json"}
        params = {"client_id": etl_config.IDMC_CLIENT_ID}
        self._extraction_fetch_url(url, headers=headers, params=params)

        IDUTransformHandler.task.delay(self.extraction_object.id)

    def handle_extract(self, retrigger: bool):
        handler_type = self.extraction_metadata.type
        logger.info(f"Starting extraction<{self.extraction_object.pk}> with metadata: {self.extraction_metadata}")
        match handler_type:
            case IDUExtractionMetadataType.QUERY:
                return self._handle_type_query()
            case _:
                typing.assert_never(handler_type)

    @staticmethod
    @app.task(bind=True, base=RetryableTask, queue=CeleryQueue.DEFAULT)
    def task(celery_task, extraction_id):  # type: ignore[reportIncompatibleMethodOverride]
        IDUExtraction(celery_task, extraction_id).handle()
