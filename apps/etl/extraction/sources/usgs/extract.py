import json
import logging
import typing
from enum import Enum

import pydantic
from celery import chord

from apps.etl.extraction.sources.base.handler import BaseExtractionV2
from apps.etl.models import ExtractionData
from apps.etl.transform.sources.usgs import USGSTransformHandler
from main.celery import CeleryQueue, app
from utils.celery import RetryableTask

logger = logging.getLogger(__name__)


class USGSExtractionMetadataType(str, Enum):
    QUERY = "QUERY"
    DETAIL = "DETAIL"
    LOSSE = "LOSSE"


class USGSExtractionMetadata(pydantic.BaseModel):
    url: str
    type: USGSExtractionMetadataType


class USGSExtraction(BaseExtractionV2[USGSExtractionMetadata]):
    """
    Handles data extraction from the USGS API
    """

    MIN_RETRY_DELAY = 60 * 5
    MAX_RETRY_DELAY = 60 * 10

    source_enum = ExtractionData.Source.USGS
    extraction_metadata_class = USGSExtractionMetadata

    def handle_type_query(self):
        # Handles base extraction from the all day url
        self._extraction_fetch_url(
            self.extraction_metadata.url,
            headers={"Content-Type": "application/json"},
        )

        # FIXME: Handle error?
        response_data = json.loads(self.extraction_object.resp_data.read())
        # FIXME: We might need to write a simple validator here
        features_list = response_data["features"]

        for feature_item in features_list:
            if "detail" not in feature_item["properties"]:
                continue
            detail_url = feature_item["properties"]["detail"]
            self.init_extraction(
                metadata=USGSExtractionMetadata(
                    url=detail_url,
                    type=USGSExtractionMetadataType.DETAIL,
                ),
                parent_extraction=self.extraction_object,
            )

    def handle_type_detail(self):
        self._extraction_fetch_url(self.extraction_metadata.url)

        with self.extraction_object.resp_data.open() as file_data:
            detail_data = json.loads(file_data.read())

        losses_tasks = []
        if "losspager" in detail_data["properties"]["products"]:
            for item in detail_data["properties"]["products"]["losspager"]:
                if "json/losses.json" in item["content"]:
                    url = item["contents"]["json/losses.json"]["url"]
                    losses_extraction_obj = self.init_extraction(
                        metadata=USGSExtractionMetadata(
                            url=url,
                            type=USGSExtractionMetadataType.LOSSE,
                        ),
                        parent_extraction=self.extraction_object,
                        add_to_queue=False,
                    )
                    losses_tasks.append(USGSExtraction.task.si(losses_extraction_obj.pk))

        if losses_tasks:
            chord(
                losses_tasks,
                # NOTE: After all losses_tasks are done, then USGSTransformHandler is called by celery
                USGSTransformHandler.task.si(self.extraction_object.pk),
            ).apply_async()
        else:
            # TODO: Or raise NoDataException()?
            USGSTransformHandler.task.delay(self.extraction_object.pk)

    def handle_type_losse(self):
        self._extraction_fetch_url(self.extraction_metadata.url)

    def handle_extract(self):
        handler_type = self.extraction_metadata.type
        logger.info(f"Starting extraction<{self.extraction_object.pk}> with metadata: {self.extraction_metadata}")
        match handler_type:
            case USGSExtractionMetadataType.QUERY:
                return self.handle_type_query()
            case USGSExtractionMetadataType.DETAIL:
                return self.handle_type_detail()
            case USGSExtractionMetadataType.LOSSE:
                return self.handle_type_losse()
            case _:
                typing.assert_never(handler_type)

    @staticmethod
    @app.task(
        bind=True,
        base=RetryableTask,
        queue=CeleryQueue.USGS_EXTRACTION,
        rate_limit="100/m",  # limit is 500 requests per 5 minute window
    )
    def task(celery_task, extraction_id):
        USGSExtraction(celery_task, extraction_id).handle()
