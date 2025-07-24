import datetime
import json
import logging
import typing
from enum import Enum

import pydantic

from apps.etl.extraction.sources.base.handler import BaseExtractionV2
from apps.etl.models import ExtractionData
from apps.etl.transform.sources.ifrc_event import IFRCEventTransformHandler
from main.celery import app
from utils.celery import RetryableTask

logger = logging.getLogger(__name__)


class IfrcEventExtractionInputMetadata(pydantic.BaseModel):
    disaster_start_date__gte: typing.Union[datetime.date, str, None]
    limit: int
    offset: int
    ordering: str
    format: typing.Literal["json"]


class IFRCExtractionMetadataType(str, Enum):
    QUERY = "QUERY"


class IFRCExtractionMetadata(pydantic.BaseModel):
    url: str
    type: IFRCExtractionMetadataType


class IFRCEventExtractionV2(BaseExtractionV2[IFRCExtractionMetadata]):
    """
    Handles data extraction from the IFRCEvent API.

    """

    source_enum = ExtractionData.Source.DREF
    extraction_metadata_class = IFRCExtractionMetadata

    def handle_type_query(self):
        url = self.extraction_metadata.url
        self._extraction_fetch_url(
            url,
            headers={"Content-Type": "application/json"},
        )
        response_data = json.loads(self.extraction_object.resp_data.read())
        IFRCEventTransformHandler.task.delay(self.extraction_object.id)
        next_url = response_data.get("next")
        if next_url:
            self.init_extraction(
                metadata=IFRCExtractionMetadata(
                    url=next_url,
                    type=IFRCExtractionMetadataType.QUERY,
                ),
            )

    def handle_extract(self, retrigger: bool):
        handler_type = self.extraction_metadata.type
        logger.info(f"Starting extraction<{self.extraction_object.pk}> with metadata: {self.extraction_metadata}")
        match handler_type:
            case IFRCExtractionMetadataType.QUERY:
                return self.handle_type_query()
            case _:
                typing.assert_never(handler_type)

    @staticmethod
    @app.task(
        bind=True,
        base=RetryableTask,
    )
    def task(celery_task, extraction_id):
        IFRCEventExtractionV2(celery_task, extraction_id).handle()
