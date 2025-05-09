import json
import logging
import typing
from enum import Enum
from typing import Optional

import pydantic

from apps.etl.extraction.sources.base.handler import BaseExtractionV2
from apps.etl.models import ExtractionData
from apps.etl.transform.sources.gdacs import GDACSTransformHandler
from main.celery import app
from main.configs import etl_config
from utils.celery import RetryableTask

logger = logging.getLogger(__name__)


class GdacsExtractionMetadataType(str, Enum):
    QUERY = "QUERY"
    DETAIL = "DETAIL"
    GEOMETRY = "GEOMETRY"
    EPISODE = "EPISODE"


class GdacsExtractionParamsMetadata(pydantic.BaseModel):
    fromDate: str
    toDate: str
    alertlevel: Optional[str] | None
    eventlist: str
    country: Optional[str] | None


class GdacsEventExtractionParamsMetadata(pydantic.BaseModel):
    eventtype: Optional[str] | None
    eventid: Optional[int] | None
    episodeid: Optional[int] | None


class GdacsEventExtractionMetadata(pydantic.BaseModel):
    url: str
    params: GdacsEventExtractionParamsMetadata
    type: GdacsExtractionMetadataType


class GdacsExtractionMetadata(pydantic.BaseModel):
    url: str
    params: typing.Optional[GdacsExtractionParamsMetadata] = None
    type: GdacsExtractionMetadataType
    event_params: typing.Optional[GdacsEventExtractionParamsMetadata] = None


class GdacsExtraction(BaseExtractionV2[GdacsExtractionMetadata]):
    MIN_RETRY_DELAY = 60 * 2
    MAX_RETRY_DELAY = 60 * 5

    source_enum = ExtractionData.Source.GDACS
    extraction_metadata_class = GdacsExtractionMetadata

    def handle_type_query(self):
        self._extraction_fetch_url(
            self.extraction_metadata.url,
            headers={"Content-Type": "application/json"},
            params=self.extraction_metadata.params,
        )

        # FIXME: Handle error?
        response_data = json.loads(self.extraction_object.resp_data.read())
        # FIXME: We might need to write a simple validator here
        features_list = response_data["features"]

        for feature_item in features_list:
            event_id = feature_item["properties"]["eventid"]
            event_detail_url = f"{etl_config.GDACS_URL}/gdacsapi/api/events/geteventdata"
            self.init_extraction(
                metadata=GdacsExtractionMetadata(
                    event_params=GdacsEventExtractionParamsMetadata(
                        eventtype=self.extraction_object.metadata["params"]["eventlist"], eventid=event_id, episodeid=None
                    ),
                    url=event_detail_url,
                    type=GdacsExtractionMetadataType.DETAIL,
                ),
                parent_extraction=self.extraction_object,
            )

    def handle_type_detail(self):
        self._extraction_fetch_url(self.extraction_metadata.url, params=self.extraction_metadata.event_params)
        with self.extraction_object.resp_data.open() as file_data:
            event_response_data = json.loads(file_data.read())

        for episode_data in event_response_data["properties"]["episodes"]:
            event_episode_url = episode_data["details"]
            event_episode_extraction_obj = self.init_extraction(
                metadata=GdacsExtractionMetadata(
                    url=event_episode_url,
                    type=GdacsExtractionMetadataType.EPISODE,
                ),
                parent_extraction=self.extraction_object,
                add_to_queue=False,
            )
            GdacsExtraction.task(event_episode_extraction_obj.id)

            event_episode_instance = ExtractionData.objects.get(id=event_episode_extraction_obj.id)
            event_episode_response_data = json.loads(event_episode_instance.resp_data.read())
            geometry_episode_url = event_episode_response_data["properties"]["url"]["geometry"]
            event_geometry_extraction_obj = self.init_extraction(
                metadata=GdacsExtractionMetadata(
                    params=None,
                    url=geometry_episode_url,
                    type=GdacsExtractionMetadataType.GEOMETRY,
                ),
                parent_extraction=event_episode_extraction_obj,
                add_to_queue=False,
            )
            GdacsExtraction.task(event_geometry_extraction_obj.id)

        GDACSTransformHandler.task.delay(self.extraction_object.id)

    def handle_type_episode(self):
        self._extraction_fetch_url(
            self.extraction_metadata.url,
            headers={"Content-Type": "application/json"},
        )

    def handle_type_geometry(self):
        self._extraction_fetch_url(
            self.extraction_metadata.url,
            headers={"Content-Type": "application/json"},
        )

    def handle_extract(self):
        handler_type = self.extraction_metadata.type
        logger.info(f"Starting extraction<{self.extraction_object.pk}> with metadata: {self.extraction_metadata}")
        match handler_type:
            case GdacsExtractionMetadataType.QUERY:
                return self.handle_type_query()
            case GdacsExtractionMetadataType.DETAIL:
                return self.handle_type_detail()
            case GdacsExtractionMetadataType.EPISODE:
                return self.handle_type_episode()
            case GdacsExtractionMetadataType.GEOMETRY:
                return self.handle_type_geometry()
            case _:
                typing.assert_never(handler_type)

    @staticmethod
    @app.task(
        bind=True,
        base=RetryableTask,
        rate_limit="50/m",
    )
    def task(celery_task, extraction_id) -> int:
        return GdacsExtraction(celery_task, extraction_id).handle()
