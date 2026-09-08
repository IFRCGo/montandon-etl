import json
import logging
import typing
from enum import Enum

import pydantic

from apps.etl.extraction.sources.base.handler import BaseExtractionV2
from apps.etl.models import ExtractionData
from apps.etl.transform.sources.cems import CEMSTransformHandler
from main.celery import CeleryQueue, app
from main.configs import etl_config
from main.logging import log_extra
from utils.celery import RetryableTask

logger = logging.getLogger(__name__)

CEMS_BASE_URL = f"{etl_config.CEMS_URL}/backend/dashboard-api"


class CEMSExtractionMetadataType(str, Enum):
    QUERY = "QUERY"
    DETAIL = "DETAIL"


class CEMSExtractionParamsMetadata(pydantic.BaseModel):
    limit: int | None = None
    offset: int | None = None
    code: str | None = None


class CEMSExtractionMetadata(pydantic.BaseModel):
    url: str
    params: CEMSExtractionParamsMetadata
    type: CEMSExtractionMetadataType


class CEMSExtraction(BaseExtractionV2[CEMSExtractionMetadata]):
    source_enum = ExtractionData.Source.CEMS
    extraction_metadata_class = CEMSExtractionMetadata

    MAX_RATE_LIMIT_RETRY_LIMIT = 15
    MIN_RETRY_DELAY = 60
    MAX_RETRY_DELAY = 600

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
            if code:
                self.init_extraction(
                    metadata=CEMSExtractionMetadata(
                        url=f"{CEMS_BASE_URL}/public-activations/?code={code}",
                        type=CEMSExtractionMetadataType.DETAIL,
                        params=CEMSExtractionParamsMetadata(code=code),
                    ),
                    queue_name=CeleryQueue.EXTRACTION,
                    parent_extraction=self.extraction_object,
                )
            else:
                logger.warning(
                    "Code missing",
                    extra=log_extra({"source": self.source_enum, "extraction": self.extraction_object}),
                )

        next_url = response_data.get("next")
        if next_url:
            self.init_extraction(
                metadata=CEMSExtractionMetadata(
                    url=next_url,
                    type=CEMSExtractionMetadataType.QUERY,
                    params=CEMSExtractionParamsMetadata(),
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

        previous_extraction = (
            ExtractionData.objects.filter(
                source=self.source_enum,
                metadata__url=self.extraction_metadata.url,
            )
            .exclude(pk=self.extraction_object.pk)
            .first()
        )
        if (
            previous_extraction is not None
            and previous_extraction.file_hash is not None
            and previous_extraction.file_hash == self.extraction_object.file_hash
        ):
            logger.info(
                "Activation content hash unchanged from previous extraction, skipping transform",
                extra=log_extra({"source": self.source_enum, "extraction": self.extraction_object}),
            )
            return

        CEMSTransformHandler.task.delay(self.extraction_object.id)

    def handle_extract(self, retrigger: bool, failed_int: int | None = None):
        handler_type = self.extraction_metadata.type
        logger.info(f"Starting extraction<{self.extraction_object.pk}> with metadata: {self.extraction_metadata}")
        match handler_type:
            case CEMSExtractionMetadataType.QUERY:
                return self.handle_type_query()
            case CEMSExtractionMetadataType.DETAIL:
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
        CEMSExtraction(celery_task, extraction_id).handle()
