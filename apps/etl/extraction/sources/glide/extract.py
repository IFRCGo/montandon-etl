import json
import logging
import typing
from enum import Enum

import pydantic
from celery import Task
from django.conf import settings

from apps.etl.extraction.sources.base.handler import BaseExtractionV2
from apps.etl.extraction.sources.base.utils import hash_file_content
from apps.etl.models import ExtractionData, Transform
from apps.etl.transform.sources.glide import GlideTransformHandler
from main.celery import CeleryQueue, app
from main.logging import log_extra
from utils.celery import RetryableTask

logger = logging.getLogger(__name__)

# Fields not used by pystac_monty GlideTransformer, so changes in them don't affect the STAC items.
# NOTE: Keep in sync with libs/pystac-monty/pystac_monty/sources/glide.py
GLIDE_HASH_IGNORED_FIELDS = {
    "homeless",
    "killed",
    "affected",
    "duration",
    "injured",
    "time",
    "id",
    "idsource",
}


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

    @classmethod
    def _compute_file_hash(cls, content: bytes) -> str | None:
        """
        Hash only the records (excluding unused fields) so changes in irrelevant fields don't trigger transforms.
        """
        try:
            records = json.loads(content)["glideset"]
        except (ValueError, KeyError, TypeError):
            logger.warning("Unexpected GLIDE response format, using raw content hash")
            return super()._compute_file_hash(content)

        if not records:
            return None

        normalized_records = sorted(
            ({key: value for key, value in record.items() if key not in GLIDE_HASH_IGNORED_FIELDS} for record in records),
            key=lambda record: str(record.get("number")),
        )
        return hash_file_content(json.dumps(normalized_records, sort_keys=True).encode("utf-8"))

    @classmethod
    def _duplicate_extra_filters(cls, extraction_object: ExtractionData) -> dict | None:
        return {"metadata__params__events": extraction_object.metadata.get("params", {}).get("events")}

    def _is_data_already_transformed(self) -> bool:
        """
        Check if the latest successful transformation used the same data (by file hash).
        """
        if self.extraction_object.file_hash is None:
            return False
        latest_transform = (
            Transform.objects.filter(
                extraction__source=self.source_enum,
                extraction__file_hash=self.extraction_object.file_hash,
                status=Transform.Status.SUCCESS,
            )
            .exclude(extraction=self.extraction_object)
            .only("id", "version")
            .order_by("-id")
            .first()
        )
        return latest_transform is not None and latest_transform.version == settings.GLIDE_TRANSFORMER_VERSION

    def handle_type_query(self, retrigger: bool = False):
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
        if self.extraction_object.source_validation_status == ExtractionData.ValidationStatus.NO_DATA:
            logger.info(f"Skipping transform for extraction<{self.extraction_object.pk}>, no records found")
            return
        if not retrigger and self._is_data_already_transformed():
            logger.info(f"Skipping transform for extraction<{self.extraction_object.pk}>, data not updated")
            return
        GlideTransformHandler.task.delay(self.extraction_object.id)

    def handle_extract(self, retrigger: bool = False, failed_int: int | None = None):
        handler_type = self.extraction_metadata.type
        logger.info(f"Starting extraction<{self.extraction_object.pk}> with metadata: {self.extraction_metadata}")
        match handler_type:
            case GlideExtractionMetadataType.QUERY:
                return self.handle_type_query(retrigger=retrigger)
            case _:
                typing.assert_never(handler_type)

    @staticmethod
    @app.task(
        bind=True,
        base=RetryableTask,
        queue=CeleryQueue.EXTRACTION,
    )
    def task(celery_task: Task, extraction_id: int):
        # NOTE : The below `extraction_id` could be both failed extraction id or normal extraction id.
        GlideExtraction(celery_task, extraction_id).handle()
