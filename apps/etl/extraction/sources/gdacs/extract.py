import json
import logging
import typing
from typing import Optional

import pydantic
from celery import chain, chord

from apps.etl.extraction.sources.base.handler import BaseExtractionV2
from apps.etl.extraction.sources.gdacs.base import GdacsExtractionMetadataType
from apps.etl.models import ExtractionData, HazardType
from apps.etl.transform.sources.gdacs import GDACSTransformHandler
from main.celery import CeleryQueue, app
from main.configs import etl_config
from main.logging import log_extra
from utils.celery import RetryableTask

logger = logging.getLogger(__name__)


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
    impact_source: typing.Optional[str] = None


class GdacsImpactData(pydantic.BaseModel):
    impact_data_list: list
    hazard_type: str

    def _handle_tc(self, impact_data: dict):
        """Handle Tropical Cyclone impact data"""
        impact_source_agency = impact_data.get("source")
        resource = impact_data.get("resource", {})
        impact_url = resource.get("timeline", None)
        if not impact_url:
            return {}
        return {"impact_url": impact_url, "source_agency": impact_source_agency}

    def handler(self):
        """Common handler for impact data"""
        transformed_impact_data = []
        for impact_data in self.impact_data_list:
            # TODO: Add a check for hazard_type while transforming
            match self.hazard_type:
                case HazardType.CYCLONE:
                    impact_data_op = self._handle_tc(impact_data)
                    if impact_data_op:
                        transformed_impact_data.append(impact_data_op)
        return transformed_impact_data


class GdacsExtraction(BaseExtractionV2[GdacsExtractionMetadata]):
    MIN_RETRY_DELAY = 60 * 2
    MAX_RETRY_DELAY = 60 * 5

    source_enum = ExtractionData.Source.GDACS
    extraction_metadata_class = GdacsExtractionMetadata

    def handle_type_query(self):
        extraction_status = self._extraction_fetch_url(
            self.extraction_metadata.url,
            headers={"Content-Type": "application/json"},
            params=self.extraction_metadata.params,
        )
        if not extraction_status:
            logger.error(
                "Failed to extract data",
                extra=log_extra({"source": self.source_enum, "extraction": self.extraction_object}),
            )
            return

        if not self.extraction_object.resp_data:
            logger.error(
                "Response data object is not available",
                extra=log_extra({"source": self.source_enum, "extraction": self.extraction_object}),
            )
            return

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
            self.init_extraction(
                metadata=metadata,
                parent_extraction=self.extraction_object,
                queue_name=CeleryQueue.EXTRACTION,
            )

    def handle_type_detail(self, retrigger: bool, failed_int: int | None = None):
        if failed_int is not None:
            failed_obj = ExtractionData.objects.filter(id=failed_int).first()
            if failed_obj.metadata.get("type") == GdacsExtractionMetadataType.DETAIL:
                ...
            elif failed_obj.metadata.get("type") == GdacsExtractionMetadataType.EPISODE:
                chord(
                    [chain(GdacsExtraction.task.s(failed_int, retrigger=retrigger), GdacsExtraction.task.s())],
                    GDACSTransformHandler.task.si(self.extraction_object.id),
                ).apply_async()
                return

            elif failed_obj.metadata.get("type") == GdacsExtractionMetadataType.GEOMETRY:  # This if for geometry failed
                chord(
                    [GdacsExtraction.task.s(failed_int)],
                    GDACSTransformHandler.task.si(self.extraction_object.id),
                ).apply_async()
                return

        extraction_status = self._extraction_fetch_url(
            self.extraction_metadata.url, params=self.extraction_metadata.event_params
        )
        if not extraction_status:
            logger.warning(
                "Failed to extract data",
                extra=log_extra({"source": self.source_enum, "extraction": self.extraction_object}),
            )
            return

        if not self.extraction_object.resp_data:
            logger.warning(
                "Response data  object is not available",
                extra=log_extra({"source": self.source_enum, "extraction": self.extraction_object}),
            )
            return
        with self.extraction_object.resp_data.open() as file_data:
            event_response_data = json.loads(file_data.read())

        episode_tasks = []
        for idx, episode_data in enumerate(event_response_data["properties"]["episodes"]):
            event_episode_url = episode_data["details"]
            event_episode_extraction_obj = self.init_extraction(
                metadata=GdacsExtractionMetadata(
                    event_params=GdacsEventExtractionParamsMetadata(
                        eventtype=event_response_data["properties"]["eventtype"],
                        episodeid=idx + 1,
                        eventid=event_response_data["properties"]["eventid"],
                    ),
                    url=event_episode_url,
                    type=GdacsExtractionMetadataType.EPISODE,
                ),
                parent_extraction=self.extraction_object,
                add_to_queue=False,
            )
            episode_tasks.append(
                chain(
                    GdacsExtraction.task.s(event_episode_extraction_obj.id, retrigger=retrigger),
                    GdacsExtraction.task.s(retrigger=retrigger),
                )
            )
        chord(episode_tasks, GDACSTransformHandler.task.si(self.extraction_object.id)).apply_async()

    def handle_type_episode(self):
        extraction_status = self._extraction_fetch_url(
            self.extraction_metadata.url,
            headers={"Content-Type": "application/json"},
        )
        if not extraction_status:
            logger.warning(
                "Failed to extract data",
                extra=log_extra({"source": self.source_enum, "extraction": self.extraction_object}),
            )
            return

        if not self.extraction_object.resp_data:
            logger.warning(
                "Response data object is not available",
                extra=log_extra({"source": self.source_enum, "extraction": self.extraction_object}),
            )
            return

        event_episode_response_data = json.loads(self.extraction_object.resp_data.read())
        geometry_episode_url = event_episode_response_data["properties"]["url"]["geometry"]
        impact_list = event_episode_response_data["properties"].get("impacts")

        geo_obj = self.init_extraction(
            metadata=GdacsExtractionMetadata(
                event_params=GdacsEventExtractionParamsMetadata(
                    eventtype=event_episode_response_data["properties"]["eventtype"],
                    episodeid=event_episode_response_data["properties"]["episodeid"],
                    eventid=event_episode_response_data["properties"]["eventid"],
                ),
                params=None,
                url=geometry_episode_url,
                type=GdacsExtractionMetadataType.GEOMETRY,
            ),
            parent_extraction=self.extraction_object,
            add_to_queue=False,
        )

        # Extract Impact data
        if impact_list:
            hazard_type = event_episode_response_data["properties"]["eventtype"]
            impact_data = GdacsImpactData(impact_data_list=impact_list, hazard_type=hazard_type)
            processed_impact_data = impact_data.handler()
            for impact_item in processed_impact_data:
                impact_obj = self.init_extraction(
                    metadata=GdacsExtractionMetadata(
                        event_params=GdacsEventExtractionParamsMetadata(
                            eventtype=event_episode_response_data["properties"]["eventtype"],
                            episodeid=event_episode_response_data["properties"]["episodeid"],
                            eventid=event_episode_response_data["properties"]["eventid"],
                        ),
                        params=None,
                        url=impact_item["impact_url"],
                        type=GdacsExtractionMetadataType.IMPACT,
                        impact_source=impact_item["source_agency"],
                    ),
                    parent_extraction=self.extraction_object,
                    add_to_queue=False,
                )
                GdacsExtraction.task(impact_obj.id)

        return geo_obj.id

    def handle_type_geometry(self):
        self._extraction_fetch_url(
            self.extraction_object.url,
            headers={"Content-Type": "application/json"},
        )

    def handle_type_impact(self):
        self._extraction_fetch_url(
            self.extraction_object.url,
            headers={"Content-Type": "application/json"},
        )

    def handle_extract(self, retrigger: bool, failed_int: int | None = None):
        handler_type = self.extraction_metadata.type
        logger.info(f"Starting extraction<{self.extraction_object.pk}> with metadata: {self.extraction_metadata}")
        match handler_type:
            case GdacsExtractionMetadataType.QUERY:
                return self.handle_type_query()
            case GdacsExtractionMetadataType.DETAIL:
                return self.handle_type_detail(retrigger=retrigger, failed_int=failed_int)
            case GdacsExtractionMetadataType.EPISODE:
                return self.handle_type_episode()
            case GdacsExtractionMetadataType.GEOMETRY:
                return self.handle_type_geometry()
            case GdacsExtractionMetadataType.IMPACT:
                return self.handle_type_impact()
            case _:
                typing.assert_never(handler_type)

    def retrigger(extraction_object: ExtractionData):
        metadata_type = extraction_object.metadata.get("type")
        if metadata_type == GdacsExtractionMetadataType.QUERY:
            GdacsExtraction.task.delay(extraction_object.id, retrigger=True, failed_int=extraction_object.id)
        if metadata_type == GdacsExtractionMetadataType.DETAIL:
            GdacsExtraction.task.delay(extraction_object.id, retrigger=True, failed_int=extraction_object.id)
        if metadata_type == GdacsExtractionMetadataType.EPISODE:
            GdacsExtraction.task.delay(extraction_object.parent.id, retrigger=True, failed_int=extraction_object.id)
        if metadata_type in [GdacsExtractionMetadataType.GEOMETRY, GdacsExtractionMetadataType.IMPACT]:
            GdacsExtraction.task.delay(extraction_object.parent.parent.id, retrigger=True, failed_int=extraction_object.id)

    @staticmethod
    @app.task(
        bind=True,
        base=RetryableTask,
        queue=CeleryQueue.EXTRACTION,
        rate_limit="100/m",
    )
    def task(celery_task, extraction_id, retrigger: bool = False, failed_int: int | None = None) -> int:
        return GdacsExtraction(celery_task, extraction_id).handle(retrigger=retrigger, failed_int=failed_int)
