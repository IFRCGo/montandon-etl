import datetime
import hashlib
import json
import logging
import tempfile
import typing
from enum import Enum

import ee
import pydantic
from ee._helpers import ServiceAccountCredentials
from ee.imagecollection import ImageCollection

from apps.etl.extraction.sources.base.handler import BaseExtractionV2
from apps.etl.extraction.sources.base.utils import manage_duplicate_file_content
from apps.etl.models import ExtractionData
from apps.etl.transform.sources.gfd import GFDTransformHandler
from main.celery import CeleryQueue, app
from main.configs import etl_config
from utils.celery import RetryableTask
from utils.requests import RateLimitError

logger = logging.getLogger(__name__)


class GFDExtractionMetadataType(str, Enum):
    QUERY = "QUERY"


class GFDExtractionMetadata(pydantic.BaseModel):
    url: str
    type: GFDExtractionMetadataType


class GFDExtraction(BaseExtractionV2[GFDExtractionMetadata]):
    """
    Handles data extraction from the GFD source
    """

    source_enum = ExtractionData.Source.GFD
    extraction_metadata_class = GFDExtractionMetadata
    FLOOD_DATASET = "GLOBAL_FLOOD_DB/MODIS_EVENTS/V1"
    num_retries = 0

    def get_json_credentials(self, content: typing.Any):
        with tempfile.NamedTemporaryFile(delete=False, mode="w") as temp_file:
            json_string = json.dumps(content, sort_keys=True)
            temp_file.write(json_string)
            temp_path = temp_file.name
        return temp_path

    def hash_json_content(self, json_data: typing.Any):
        """Hashes a JSON object using SHA256."""
        json_string = json.dumps(json_data, sort_keys=True)
        return hashlib.sha256(json_string.encode()).hexdigest()

    def store_extraction_data(
        self,
        extraction_object: ExtractionData,
        response_data: list,
        file_extension: str = "json",
        content_type: str | None = None,
    ):
        """
        Save extracted data into database. Checks for duplicate content using hashing.
        """
        file_name = f"{extraction_object.source}.{file_extension}"
        extraction_object.resp_data_type = content_type or "application/json"

        extraction_object.save()

        # Validate the non empty response data.
        if response_data:
            # manage duplicate file content.
            hash_content = self.hash_json_content(response_data)
            manage_duplicate_file_content(
                source=extraction_object.source,
                hash_content=hash_content,
                instance=extraction_object,
                response_data=response_data,
                file_name=file_name,
            )
        return extraction_object

    def _pull_data(self, collection: ImageCollection, batch_size: int = 500) -> list[typing.Any]:
        """Retrieve flood metadata in batches to avoid memory issues."""
        total_size: int | None = collection.size().getInfo()

        if total_size is None:
            return []

        all_data: list[typing.Any] = []
        for i in range(0, total_size, batch_size):
            batch: list[typing.Any] | None = collection.toList(batch_size, i).getInfo()
            if batch is not None:
                all_data.extend([feature for feature in batch])

        return all_data

    def _get_flood_data(self, start_date: datetime.date | None = None, end_date: datetime.date | None = None):
        # Set up authentication
        service_account = etl_config.GFD_SERVICE_ACCOUNT

        # # Decode the earthengine credential
        decoded_json = etl_config.GFD_CREDENTIAL
        credential_file_path = self.get_json_credentials(decoded_json)

        # Authenticate
        credentials = ServiceAccountCredentials(service_account, credential_file_path)

        try:
            ee.Initialize(credentials)

            # Load Global Flood Database (GFD)
            flood_img_collection = ImageCollection(self.FLOOD_DATASET)

            # Filter flood events by date
            if start_date and end_date:
                flood_img_collection = flood_img_collection.filterDate(str(start_date), str(end_date))

            flood_data = self._pull_data(collection=flood_img_collection)
        except Exception:
            self.num_retries += 1
            raise RateLimitError(retry_after=self.num_retries)
        return flood_data

    def _handle_type_query(self):
        flood_data = self._get_flood_data()
        self.extraction_object.resp_code = 200
        response_data_obj = self.store_extraction_data(
            extraction_object=self.extraction_object,
            response_data=flood_data,
        )
        if response_data_obj:
            logger.info("Data extracted successfully")
            # Run the transformer task
            GFDTransformHandler.task.delay(self.extraction_object.id)
        logger.warning("No data found in response")

    def handle_extract(self):
        handler_type = self.extraction_metadata.type
        logger.info(f"Starting extraction<{self.extraction_object.pk}> with metadata: {self.extraction_metadata}")
        match handler_type:
            case GFDExtractionMetadataType.QUERY:
                return self._handle_type_query()
            case _:
                typing.assert_never(handler_type)

    @staticmethod
    @app.task(bind=True, base=RetryableTask, queue=CeleryQueue.DEFAULT)
    def task(celery_task, extraction_id):  # type: ignore[reportIncompatibleMethodOverride]
        GFDExtraction(celery_task, extraction_id).handle()
