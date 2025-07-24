import json
import logging
import typing
from enum import Enum
from typing import Optional

import pydantic
from celery import chain, chord

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

    def handle_type_query(self, retrigger: bool):
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
            eventtype = self.extraction_object.metadata.get("params").get("eventlist")
            metadata = GdacsExtractionMetadata(
                event_params=GdacsEventExtractionParamsMetadata(eventtype=eventtype, eventid=event_id, episodeid=None),
                url=event_detail_url,
                type=GdacsExtractionMetadataType.DETAIL,
            )

            if not retrigger:
                self.init_extraction(
                    metadata=metadata,
                    parent_extraction=self.extraction_object,
                )
            else:
                extraction_object = ExtractionData.objects.filter(url=event_detail_url, metadata=metadata.dict()).first()
                if not extraction_object:
                    extraction_object = self.init_extraction(
                        metadata=metadata,
                        parent_extraction=self.extraction_object,
                    )

                GdacsExtraction.task.delay(extraction_object.pk, retrigger=retrigger)

    def handle_type_detail(self, retrigger: bool):
        self._extraction_fetch_url(self.extraction_metadata.url, params=self.extraction_metadata.event_params)
        with self.extraction_object.resp_data.open() as file_data:
            event_response_data = json.loads(file_data.read())

        episode_tasks = []
        for episode_data in event_response_data["properties"]["episodes"]:
            event_episode_url = episode_data["details"]
            if not retrigger:
                event_episode_extraction_obj = self.init_extraction(
                    metadata=GdacsExtractionMetadata(
                        url=event_episode_url,
                        type=GdacsExtractionMetadataType.EPISODE,
                    ),
                    parent_extraction=self.extraction_object,
                    add_to_queue=False,
                )

                self.init_extraction(
                    metadata=GdacsExtractionMetadata(
                        params=None,
                        url="",  # url is set in handle_type_episode method after data extraction
                        type=GdacsExtractionMetadataType.GEOMETRY,
                    ),
                    parent_extraction=event_episode_extraction_obj,
                    add_to_queue=False,
                )

            else:
                event_episode_extraction_obj = ExtractionData.objects.filter(
                    url=event_episode_url,
                    metadata=GdacsExtractionMetadata(
                        url=event_episode_url,
                        type=GdacsExtractionMetadataType.EPISODE,
                    ).dict(),
                ).first()
                if not event_episode_extraction_obj:
                    event_episode_extraction_obj = self.init_extraction(
                        metadata=GdacsExtractionMetadata(
                            url=event_episode_url,
                            type=GdacsExtractionMetadataType.EPISODE,
                        ),
                        parent_extraction=self.extraction_object,
                        add_to_queue=False,
                    )
                    self.init_extraction(
                        metadata=GdacsExtractionMetadata(
                            params=None,
                            url="",  # url is set in handle_type_episode method after data extraction
                            type=GdacsExtractionMetadataType.GEOMETRY,
                        ),
                        parent_extraction=event_episode_extraction_obj,
                        add_to_queue=False,
                    )

            episode_tasks.append(chain(GdacsExtraction.task.s(event_episode_extraction_obj.id), GdacsExtraction.task.s()))

        chord(episode_tasks, GDACSTransformHandler.task.si(self.extraction_object.id)).apply_async()

    def handle_type_episode(self):
        self._extraction_fetch_url(
            self.extraction_metadata.url,
            headers={"Content-Type": "application/json"},
        )

        # geometry url is set here so that _extraction_fetch_url() can be called next
        event_episode_response_data = json.loads(self.extraction_object.resp_data.read())
        geometry_episode_url = event_episode_response_data["properties"]["url"]["geometry"]

        geo_obj = ExtractionData.objects.filter(
            parent=self.extraction_object, metadata__type=GdacsExtractionMetadataType.GEOMETRY
        ).first()
        metadata = geo_obj.metadata
        metadata["url"] = geometry_episode_url

        geo_obj.url = geometry_episode_url
        geo_obj.metadata = metadata
        geo_obj.save(update_fields=["url", "metadata"])

        return geo_obj.id

    def handle_type_geometry(self):
        self._extraction_fetch_url(
            self.extraction_object.url,
            headers={"Content-Type": "application/json"},
        )

    def handle_extract(self, retrigger: bool):
        handler_type = self.extraction_metadata.type
        logger.info(f"Starting extraction<{self.extraction_object.pk}> with metadata: {self.extraction_metadata}")
        match handler_type:
            case GdacsExtractionMetadataType.QUERY:
                return self.handle_type_query(retrigger=retrigger)
            case GdacsExtractionMetadataType.DETAIL:
                return self.handle_type_detail(retrigger=retrigger)
            case GdacsExtractionMetadataType.EPISODE:
                return self.handle_type_episode()
            case GdacsExtractionMetadataType.GEOMETRY:
                return self.handle_type_geometry()
            case _:
                typing.assert_never(handler_type)

    def retrigger(extraction_object):
        metadata_type = extraction_object.metadata.get("type")
        if metadata_type == GdacsExtractionMetadataType.QUERY:
            GdacsExtraction.task.delay(extraction_object.id, retrigger=True)
        if metadata_type == GdacsExtractionMetadataType.DETAIL:
            GdacsExtraction.task.delay(extraction_object.id, retrigger=True)
        if metadata_type == GdacsExtractionMetadataType.EPISODE:
            GdacsExtraction.task.delay(extraction_object.parent.id, retrigger=True)
        if metadata_type == GdacsExtractionMetadataType.GEOMETRY:
            GdacsExtraction.task.delay(extraction_object.parent.parent.id, retrigger=True)

    @staticmethod
    @app.task(
        bind=True,
        base=RetryableTask,
        rate_limit="100/m",
    )
    def task(celery_task, extraction_id, retrigger: bool = False) -> int:
        return GdacsExtraction(celery_task, extraction_id).handle(retrigger=retrigger)
