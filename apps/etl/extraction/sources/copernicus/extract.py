import json
import logging
import typing
from enum import Enum

import pydantic

from apps.etl.extraction.sources.base.handler import BaseExtractionV2
from apps.etl.models import ExtractionData
from apps.etl.transform.sources.copernicus import CopernicusTransformHandler
from main.celery import CeleryQueue, app
from main.configs import etl_config
from main.logging import log_extra
from utils.celery import RetryableTask

logger = logging.getLogger(__name__)

COPERNICUS_BASE_URL = f"{etl_config.COPERNICUS_URL}/backend/dashboard-api"


class CopernicusExtractionMetadataType(str, Enum):
    QUERY = "QUERY"
    DETAIL = "DETAIL"


class CopernicusExtractionParamsMetadata(pydantic.BaseModel):
    limit: int | None = None
    offset: int | None = None
    code: str | None = None


class CopernicusExtractionMetadata(pydantic.BaseModel):
    url: str
    params: CopernicusExtractionParamsMetadata
    type: CopernicusExtractionMetadataType


class CopernicusExtraction(BaseExtractionV2[CopernicusExtractionMetadata]):
    source_enum = ExtractionData.Source.COPERNICUS
    extraction_metadata_class = CopernicusExtractionMetadata

    @classmethod
    def _duplicate_extra_filters(cls, extraction_object: ExtractionData) -> dict | None:
        return {"metadata__url": extraction_object.metadata.get("url")}

    def handle_type_query(self):
        extraction_status = self._extraction_fetch_url(
            self.extraction_metadata.url,
            headers={"Content-Type": "application/json"},
            params=self.extraction_metadata.params.model_dump(exclude_none=True),
        )
        if not extraction_status:
            logger.error(
                "Failed to extract data",
                extra=log_extra({"source": self.source_enum, "extraction": self.extraction_object}),
            )
            return

        if not self.extraction_object.resp_data:
            logger.error(
                "Response data object is not available",
                extra=log_extra({"source": self.source_enum, "extraction": self.extraction_object}),
            )
            return

        response_data = json.loads(self.extraction_object.resp_data.read())
        for obj in response_data.get("results", []):
            code = obj.get("code")
            self.init_extraction(
                metadata=CopernicusExtractionMetadata(
                    url=f"{COPERNICUS_BASE_URL}/public-activations/?code={code}",
                    type=CopernicusExtractionMetadataType.DETAIL,
                    params=CopernicusExtractionParamsMetadata(code=code),
                ),
                queue_name=CeleryQueue.EXTRACTION,
                parent_extraction=self.extraction_object,
            )

        next_url = response_data.get("next")
        if next_url:
            self.init_extraction(
                metadata=CopernicusExtractionMetadata(
                    url=next_url,
                    type=CopernicusExtractionMetadataType.QUERY,
                    params=CopernicusExtractionParamsMetadata(),
                ),
                queue_name=CeleryQueue.EXTRACTION,
            )

    def handle_type_detail(self):
        extraction_status = self._extraction_fetch_url(
            self.extraction_metadata.url,
            headers={"Content-Type": "application/json"},
        )
        if not extraction_status:
            logger.error(
                "Failed to extract data",
                extra=log_extra({"source": self.source_enum, "extraction": self.extraction_object}),
            )
            return
        CopernicusTransformHandler.task.delay(self.extraction_object.id)

    def handle_extract(self, retrigger: bool, failed_int: int | None = None):
        handler_type = self.extraction_metadata.type
        logger.info(f"Starting extraction<{self.extraction_object.pk}> with metadata: {self.extraction_metadata}")
        match handler_type:
            case CopernicusExtractionMetadataType.QUERY:
                return self.handle_type_query()
            case CopernicusExtractionMetadataType.DETAIL:
                return self.handle_type_detail()
            case _:
                typing.assert_never(handler_type)

    @staticmethod
    @app.task(
        bind=True,
        base=RetryableTask,
        queue=CeleryQueue.EXTRACTION,
    )
    def task(celery_task, extraction_id: int):
        CopernicusExtraction(celery_task, extraction_id).handle()
