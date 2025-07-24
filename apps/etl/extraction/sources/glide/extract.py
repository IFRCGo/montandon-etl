import logging
import typing
from enum import Enum

import pydantic
from celery import Task

from apps.etl.extraction.sources.base.handler import BaseExtractionV2
from apps.etl.models import ExtractionData
from apps.etl.transform.sources.glide import GlideTransformHandler
from main.celery import app
from main.logging import log_extra
from utils.celery import RetryableTask

logger = logging.getLogger(__name__)


class GlideExtractionMetadataType(str, Enum):
    QUERY = "QUERY"


class GlideExtractionParamsMetadata(pydantic.BaseModel):
    fromyear: int | None
    frommonth: int | None
    fromday: int | None
    toyear: int | None
    tomonth: int | None
    today: int | None
    events: str | None


class GlideExtractionMetadata(pydantic.BaseModel):
    url: str
    type: GlideExtractionMetadataType
    params: GlideExtractionParamsMetadata


class GlideExtraction(BaseExtractionV2[GlideExtractionMetadata]):
    source_enum = ExtractionData.Source.GLIDE
    extraction_metadata_class = GlideExtractionMetadata

    def handle_type_query(self):
        url = self.extraction_metadata.url
        params = self.extraction_metadata.params
        headers = {"Content-Type": "application/json"}
        extraction_status = self._extraction_fetch_url(url, params, headers)
        if not extraction_status:
            logger.warning(
                "Failed to extract data",
                extra=log_extra({"source": self.source_enum, "extraction": self.extraction_object}),
            )
            return
        GlideTransformHandler.task.delay(self.extraction_object.id)

    def handle_extract(self, retrigger: bool = False):
        handler_type = self.extraction_metadata.type
        logger.info(f"Starting extraction<{self.extraction_object.pk}> with metadata: {self.extraction_metadata}")
        match handler_type:
            case GlideExtractionMetadataType.QUERY:
                return self.handle_type_query()
            case _:
                typing.assert_never(handler_type)

    @staticmethod
    @app.task(
        bind=True,
        base=RetryableTask,
    )
    def task(celery_task: Task, extraction_id: int) -> int:
        GlideExtraction(celery_task, extraction_id).handle()
