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
from apps.etl.transform.sources.emdat import EMDATTransformHandler
from main.celery import CeleryQueue, app
from main.configs import etl_config
from utils.celery import RetryableTask

logger = logging.getLogger(__name__)

# Fields not used by pystac_monty EMDATTransformer, so changes in them don't affect the STAC items.
# NOTE: Keep in sync with libs/pystac-monty/pystac_monty/sources/emdat.py
EMDAT_HASH_IGNORED_FIELDS = {
    "group",
    "subgroup",
    "external_ids",
    "subregion",
    "region",
    "origin",
    "associated_types",
    "ofda_response",
    "appeal",
    "declaration",
    "aid_contribution",
    "river_basin",
    "reconstr_dam",
    "reconstr_dam_adj",
    "insur_dam",
    "insur_dam_adj",
    "total_dam_adj",
    "cpi",
    "entry_date",
    "last_update",
}


class EmdatExtractionMetadataType(str, Enum):
    QUERY = "QUERY"


class EmdatExtractionParamsMetadata(pydantic.BaseModel):
    limit: int | None
    from_: int | None
    to: int | None
    include_hist: bool | None
    classif: list


class EmdatExtractionMetadata(pydantic.BaseModel):
    url: str
    params: EmdatExtractionParamsMetadata
    type: EmdatExtractionMetadataType


class EmdatExtraction(BaseExtractionV2[EmdatExtractionMetadata]):
    source_enum = ExtractionData.Source.EMDAT
    extraction_metadata_class = EmdatExtractionMetadata

    @classmethod
    def _compute_file_hash(cls, content: bytes) -> str | None:
        """
        Hash only the records (excluding the response envelope eg: info.timestamp and the ignored fields)
        """
        try:
            records = json.loads(content)["data"]["public_emdat"]["data"]
        except (ValueError, KeyError, TypeError):
            logger.warning("Unexpected EMDAT response format, using raw content hash")
            return super()._compute_file_hash(content)

        if not records:
            return None

        normalized_records = sorted(
            ({key: value for key, value in record.items() if key not in EMDAT_HASH_IGNORED_FIELDS} for record in records),
            key=lambda record: str(record.get("disno")),
        )
        return hash_file_content(json.dumps(normalized_records, sort_keys=True).encode("utf-8"))

    @classmethod
    def _duplicate_extra_filters(cls, extraction_object: ExtractionData) -> dict | None:
        return {"metadata__params": extraction_object.metadata.get("params")}

    def _is_data_already_transformed(self) -> bool:
        """
        Check if the latest successful transformation for the same query used the same data.
        """
        latest_transform = (
            Transform.objects.filter(
                extraction__source=self.source_enum,
                extraction__metadata__params=self.extraction_object.metadata.get("params"),
                status=Transform.Status.SUCCESS,
            )
            .exclude(extraction=self.extraction_object)
            .select_related("extraction")
            .only("id", "version", "extraction__file_hash")
            .order_by("-id")
            .first()
        )
        return (
            latest_transform is not None
            and self.extraction_object.file_hash is not None
            and latest_transform.extraction.file_hash == self.extraction_object.file_hash
            and latest_transform.version == settings.EMDAT_TRANSFORMER_VERSION
        )

    def handle_type_query(self, retrigger: bool = False):
        from apps.etl.etl_tasks.emdat import QUERY

        url = self.extraction_metadata.url
        params = self.extraction_metadata.params
        headers = {"Authorization": etl_config.EMDAT_AUTHORIZATION_KEY}
        payload = {"query": QUERY, "variables": params.model_dump()}
        payload["variables"]["from"] = payload["variables"].pop("from_")
        self._extraction_fetch_graphql(url, payload, headers)

        if self.extraction_object.source_validation_status == ExtractionData.ValidationStatus.NO_DATA:
            logger.info(f"Skipping transform for extraction<{self.extraction_object.pk}>, no records found")
            return
        if not retrigger and self._is_data_already_transformed():
            logger.info(f"Skipping transform for extraction<{self.extraction_object.pk}>, data not updated")
            return
        EMDATTransformHandler.task.delay(self.extraction_object.id)

    def handle_extract(self, retrigger: bool, failed_int: int | None = None):
        handler_type = self.extraction_metadata.type
        logger.info(f"Starting extraction<{self.extraction_object.pk}> with metadata: {self.extraction_metadata}")
        match handler_type:
            case EmdatExtractionMetadataType.QUERY:
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
        EmdatExtraction(celery_task, extraction_id).handle()
