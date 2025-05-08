import logging
import typing
from enum import Enum

import pydantic
from celery import Task

from apps.etl.extraction.sources.base.handler import BaseExtractionV2
from apps.etl.models import ExtractionData
from main.celery import CeleryQueue, app
from main.configs import etl_config
from utils.celery import RetryableTask

logger = logging.getLogger(__name__)


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

    def handle_type_query(self):
        from apps.etl.etl_tasks.emdat import QUERY

        logger.info(f"Starting extraction<{self.extraction_object.pk}> with metadata: {self.extraction_metadata}")
        url = self.extraction_metadata.url
        params = self.extraction_metadata.params
        headers = {"Authorization": etl_config.EMDAT_AUTHORIZATION_KEY}
        payload = {"query": QUERY, "variables": params.model_dump()}
        payload["variables"]["from"] = payload["variables"].pop("from_")
        self._extraction_fetch_graphql(url, payload, headers)

        # with self.extraction_object.resp_data.open() as file_data:
        #     data = json.loads(file_data.read())
        # if not data["data"]["public_emdat"]:
        #     self.handle_extract_error(NoDataException)

        return self.extraction_object.id

    def handle_extract(self):
        handler_type = self.extraction_metadata.type
        logger.info(f"Starting extraction<{self.extraction_object.pk}> with metadata: {self.extraction_metadata}")
        match handler_type:
            case EmdatExtractionMetadataType.QUERY:
                return self.handle_type_query()
            case _:
                typing.assert_never(handler_type)

    @staticmethod
    @app.task(
        bind=True,
        base=RetryableTask,
        queue=CeleryQueue.DEFAULT,
    )
    def task(celery_task: Task, extraction_id: int) -> int:
        return EmdatExtraction(celery_task, extraction_id).handle()
