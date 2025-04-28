import logging

import pydantic

from apps.etl.extraction.sources.base.handler import BaseExtractionV2
from apps.etl.models import ExtractionData
from main.celery import CeleryQueue, app
from utils.celery import RetryableTask

logger = logging.getLogger(__name__)


class GlideExtractionMetadata(pydantic.BaseModel):
    url: str


class GlideExtraction(BaseExtractionV2[GlideExtractionMetadata]):
    source_enum = ExtractionData.Source.GLIDE
    extraction_metadata_class = GlideExtractionMetadata

    def handle_extract(self):
        logger.info(f"Starting extraction<{self.extraction_object.pk}> with metadata: {self.extraction_metadata}")
        url = self.extraction_metadata.url
        headers = {"Content-Type": "application/json"}
        self._extraction_fetch_url(url, headers)

    @staticmethod
    @app.task(
        bind=True,
        base=RetryableTask,
        queue=CeleryQueue.DEFAULT,
    )
    def task(celery_task, extraction_id):
        GlideExtraction(celery_task, extraction_id).handle()
