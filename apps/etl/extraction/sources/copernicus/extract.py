import json
import logging
import typing
from enum import Enum

import pydantic
from django.db.models import F

from apps.etl.extraction.sources.base.handler import BaseExtractionV2
from apps.etl.models import ExtractionData
from apps.etl.transform.sources.copernicus import CopernicusTransformHandler
from main.celery import CeleryQueue, app
from main.configs import etl_config
from main.logging import log_extra
from utils.celery import RetryableTask
from utils.requests import RateLimitError

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

    MAX_RATE_LIMIT_RETRY_LIMIT = 15
    MIN_RETRY_DELAY = 60
    MAX_RETRY_DELAY = 600

    def handle_extract_error(self, exc: Exception):
        if not isinstance(exc, RateLimitError):
            return super().handle_extract_error(exc)

        retries = self.celery_task.request.retries
        if retries >= self.MAX_RATE_LIMIT_RETRY_LIMIT:
            logger.warning(
                "Max rate-limit retries reached for Copernicus extraction.",
                extra=log_extra({"source": self.source_enum, "extraction": self.extraction_object}),
            )
            self.extraction_object.mark_as_ended(ExtractionData.Status.FAILED)
            return

        if exc.retry_after:
            try:
                delay = max(self.MIN_RETRY_DELAY, int(exc.retry_after))
            except ValueError:
                delay = self.celery_task.exponential_backoff_with_jitter(
                    retries, min_delay=self.MIN_RETRY_DELAY, max_delay=self.MAX_RETRY_DELAY
                )
        else:
            delay = self.celery_task.exponential_backoff_with_jitter(
                retries, min_delay=self.MIN_RETRY_DELAY, max_delay=self.MAX_RETRY_DELAY
            )

        logger.warning(
            f"Copernicus rate limited. Retrying in {delay:.2f}s (attempt {retries + 1}/{self.MAX_RATE_LIMIT_RETRY_LIMIT}).",
            extra=log_extra({"source": self.source_enum, "extraction": self.extraction_object}),
        )
        self.extraction_object.mark_as_ended(ExtractionData.Status.ON_RETRY)
        ExtractionData.objects.filter(pk=self.extraction_object.pk).update(attempt_no=F("attempt_no") + 1)
        raise self.celery_task.retry(exc=exc, countdown=delay)

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
