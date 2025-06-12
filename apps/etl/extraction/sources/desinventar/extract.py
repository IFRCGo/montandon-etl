import json
import logging
import typing
from enum import Enum

import pydantic

from apps.etl.extraction.sources.base.handler import BaseExtractionV2
from apps.etl.models import ExtractionData
from apps.etl.transform.sources.desinventar import DesinventarTransformHandler
from main.celery import app
from utils.celery import RetryableTask

logger = logging.getLogger(__name__)


class DesInventarExtractionInputMetadata(pydantic.BaseModel):
    country_code: str
    iso3: str


class DesInventarMetadataType(str, Enum):
    QUERY = "QUERY"


class DesInventarExtractionParamsMetadata(pydantic.BaseModel):
    country_code: str
    iso3: str


class DesInventarExtractionMetadata(pydantic.BaseModel):
    url: str
    type: DesInventarMetadataType
    params: DesInventarExtractionParamsMetadata


class DesInventarExtraction(BaseExtractionV2[DesInventarExtractionMetadata]):
    """
    Handles data extraction from the Desinventar API.
    """

    source_enum = ExtractionData.Source.DESINVENTAR
    extraction_metadata_class = DesInventarExtractionMetadata

    def handle_type_query(self):
        self._extraction_fetch_url(
            url=self.extraction_metadata.url,
            params=json.dumps(self.extraction_metadata.params.model_dump()),
            timeout=180,
            file_extension="zip",
        )

        DesinventarTransformHandler.task.delay(self.extraction_object.id)

    def handle_extract(self, retrigger: bool):
        handler_type = self.extraction_metadata.type
        logger.info(f"Starting extraction<{self.extraction_object.pk}> with metadata: {self.extraction_metadata}")
        match handler_type:
            case DesInventarMetadataType.QUERY:
                return self.handle_type_query()
            case _:
                typing.assert_never(handler_type)

    @staticmethod
    @app.task(
        bind=True,
        base=RetryableTask,
    )
    def task(celery_task, extraction_id):
        DesInventarExtraction(celery_task, extraction_id).handle()
