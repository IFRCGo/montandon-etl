import logging

import pydantic
import requests

from apps.etl.models import ExtractionData
from main.configs import etl_config
from main.logging import log_extra

from apps.etl.extraction.sources.base.handler import BaseExtractionV2
from apps.etl.models import ExtractionData
from main.celery import CeleryQueue, app
from utils.celery import RetryableTask

logger = logging.getLogger(__name__)


class EmdatExtractionMetadata(pydantic.BaseModel):
    limit: int | None
    from_: int | None
    to: int | None
    include_hist: bool | None
    classif: list
    url: str


class EmdatExtraction(BaseExtractionV2[EmdatExtractionMetadata]):
    source_enum = ExtractionData.Source.EMDAT
    extraction_metadata_class = EmdatExtractionMetadata

    def _extraction_fetch_url(self, url, headers):
        from apps.etl.etl_tasks.emdat import QUERY

        input_metadata = self.extraction_object.metadata
        paylod = {"query": QUERY, "variables": input_metadata}
        paylod["variables"]["from"] = paylod["variables"].pop("from_")

        response = requests.post(url, json=paylod, headers=headers)
        response.raise_for_status()
        self.extraction_object.resp_code = response.status_code

        if response.status_code in [200, 204]:
            response_data = self._extraction_store_data(
                extraction_object=self.extraction_object,
                response=response,
            )
            # Check if response contains data
            if response_data:
                logger.info("Data extracted successfully")
                return True
            logger.warning("No data found in response")
        return False

    def handle_extract(self):
        logger.info(f"Starting extraction<{self.extraction_object.pk}> with metadata: {self.extraction_metadata}")
        # url = f"{etl_config.EMDAT_URL}/v1"
        url = self.extraction_object.metadata["url"]
        headers = {"Authorization": etl_config.EMDAT_AUTHORIZATION_KEY}
        self._extraction_fetch_url(url, headers)

    @staticmethod
    @app.task(
        bind=True,
        base=RetryableTask,
        queue=CeleryQueue.DEFAULT,
    )
    def task(celery_task, extraction_id):
        print("Emdat Ext task")
        EmdatExtraction(celery_task, extraction_id).handle()

