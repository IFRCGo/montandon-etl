import json
import logging
import typing
from enum import Enum

import pydantic
from celery import Task

from apps.etl.extraction.sources.base.handler import BaseExtractionV2
from apps.etl.models import ExtractionData
from apps.etl.transform.sources.alert_hub import AlertHubTransformHandler
from main.celery import CeleryQueue, app
from utils.celery import RetryableTask

logger = logging.getLogger(__name__)


class AlertHubExtractionMetadataType(str, Enum):
    QUERY = "QUERY"
    PAGINATION = "PAGINATION"


class AlertHubExtractionParamsMetadata(pydantic.BaseModel):
    start: str
    end: str
    limit: int
    offset: int


class AlertHubExtractionMetadata(pydantic.BaseModel):
    url: str
    params: AlertHubExtractionParamsMetadata
    type: AlertHubExtractionMetadataType


class AlertHubExtraction(BaseExtractionV2[AlertHubExtractionMetadata]):
    source_enum = ExtractionData.Source.ALERTHUB
    extraction_metadata_class = AlertHubExtractionMetadata

    def build_alerts_variables(self, meta: AlertHubExtractionMetadata) -> dict:
        return {
            "pagination": {
                "limit": meta.params.limit,
                "offset": meta.params.offset,
            },
            "filters": {
                "sent": {
                    "gte": meta.params.start,
                    "lt": meta.params.end,
                }
            },
        }

    def fetch(self):
        from apps.etl.etl_tasks.alert_hub import QUERY

        payload = {"query": QUERY, "variables": self.build_alerts_variables(self.extraction_metadata)}
        return self._extraction_fetch_graphql(self.extraction_metadata.url, payload)

    def handle_type_query(self):
        self.fetch()
        limit = 10
        extraction_content = json.load(self.extraction_object.resp_data)
        count = extraction_content["data"]["public"]["historicalAlerts"]["count"]

        if self.extraction_object.resp_data:
            for i in range(0, count, limit):
                self.init_extraction(
                    metadata=AlertHubExtractionMetadata(
                        url=self.extraction_metadata.url,
                        params=AlertHubExtractionParamsMetadata(
                            limit=limit,
                            offset=i,
                            start=self.extraction_metadata.params.start,
                            end=self.extraction_metadata.params.end,
                        ),
                        type=AlertHubExtractionMetadataType.PAGINATION,
                    ),
                    queue_name=CeleryQueue.EXTRACTION,
                    parent_extraction=self.extraction_object,
                )

    def handle_paginated_data(self):
        self.fetch()
        AlertHubTransformHandler.task.delay(self.extraction_object.id)

    def handle_extract(self, retrigger: bool, failed_int: int | None = None):
        handler_type = self.extraction_metadata.type
        logger.info(f"Starting extraction<{self.extraction_object.pk}> with metadata: {self.extraction_metadata}")
        match handler_type:
            case AlertHubExtractionMetadataType.QUERY:
                return self.handle_type_query()
            case AlertHubExtractionMetadataType.PAGINATION:
                return self.handle_paginated_data()
            case _:
                typing.assert_never(handler_type)

    @staticmethod
    @app.task(
        bind=True,
        base=RetryableTask,
        queue=CeleryQueue.EXTRACTION,
        rate_limit="10/m",
    )
    def task(celery_task: Task, extraction_id: int):
        AlertHubExtraction(celery_task, extraction_id).handle()
