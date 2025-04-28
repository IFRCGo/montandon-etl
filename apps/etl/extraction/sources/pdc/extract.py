import json
import logging
import typing
from enum import Enum

import pydantic
from celery import chord

from apps.etl.extraction.sources.base.handler import BaseExtractionV2
from apps.etl.models import ExtractionData, HazardType
from apps.etl.transform.sources.pdc import PDCTransformHandler
from main.celery import app
from main.configs import etl_config
from utils.celery import RetryableTask

logger = logging.getLogger(__name__)


class PDCExtractionMetaDataType(str, Enum):
    POLYGON = "POLYGON"
    EXPOSURE_LIST = "EXPOSURE_LIST"
    EXPOSURE_DETAIL = "EXPOSURE_DETAIL"
    HAZARD = "HAZARD"


class PDCExtractionMetadata(pydantic.BaseModel):
    extraction_args: typing.Optional[dict] | None = None
    transform_args: typing.Optional[dict] | None = None
    url: str
    type: PDCExtractionMetaDataType


class PdcPolygonInputMetadata(pydantic.BaseModel):
    hazard_uuid: str
    hazard_type_id: str


class PdcExposureInputMetadata(pydantic.BaseModel):
    exposure_id: str | None = None
    hazard_uuid: str | None = None
    geojson_id: int | None = None


class Pagination(pydantic.BaseModel):
    page: int
    pagesize: int


class Restriction(pydantic.BaseModel):
    searchType: str
    createDate: typing.Optional[str] | None = None
    typeId: typing.Optional[str] | None = None


class PdcHazardInputMetadata(pydantic.BaseModel):
    pagination: Pagination
    restrictions: typing.List[typing.List[Restriction]]


HAZARD_TYPE_MAP = {
    "AVALANCHE": HazardType.OTHER,
    "DROUGHT": HazardType.DROUGHT,
    "EARTHQUAKE": HazardType.EARTHQUAKE,
    "EXTREMETEMPERATURE": HazardType.EXTREME_TEMPERATURE,
    "FLOOD": HazardType.FLOOD,
    "HIGHWIND": HazardType.WIND,
    "LANDSLIDE": HazardType.LANDSLIDE,
    "SEVEREWEATHER": HazardType.OTHER,
    "STORM": HazardType.STORM,
    "TORNADO": HazardType.TORNADO,
    "CYCLONE": HazardType.CYCLONE,
    "TSUNAMI": HazardType.TSUNAMI,
    "VOLCANO": HazardType.VOLCANO,
    "WILDFIRE": HazardType.WILDFIRE,
    "WINTERSTORM": HazardType.OTHER,
}


class PDCExtractionV2(BaseExtractionV2[PDCExtractionMetadata]):
    """
    PDC Extraction task for PDC Sentry.
    """

    source_enum = ExtractionData.Source.PDC
    extraction_metadata_class = PDCExtractionMetadata

    def handle_type_hazard(self):
        self._extraction_fetch_url(
            self.extraction_metadata.url,
            data=json.dumps(self.extraction_metadata.extraction_args),
            headers={
                "Authorization": f"Bearer {etl_config.PDC_SENTRY_AUTHORIZATION_KEY}",
                "Content-Type": "application/json",
            },
            method="post",
        )
        response_data = json.loads(self.extraction_object.resp_data.read())

        for item in response_data:
            self.init_extraction(
                metadata=PDCExtractionMetadata(
                    url=f"{etl_config.PDC_SENTRY_BASE_URL}/hp_srv/services/hazard/{item['uuid']}/exposure",
                    type=PDCExtractionMetaDataType.EXPOSURE_LIST,
                    extraction_args={
                        "hazard_uuid": item["uuid"],
                        "hazard_id": item["hazard_ID"],
                    },
                ),
                parent_extraction=self.extraction_object,
            )

    def handle_exposure_list(self):
        self._extraction_fetch_url(
            self.extraction_metadata.url,
            headers={
                "Authorization": f"Bearer {etl_config.PDC_SENTRY_AUTHORIZATION_KEY}",
                "Content-Type": "application/json",
            },
        )
        if not self.extraction_object.resp_data:
            return None

        response_data = json.loads(self.extraction_object.resp_data.read())
        if not response_data:
            return None

        # Create geojson only once (if all exposures share the same hazard_id)
        geo_json_obj = self.init_extraction(
            metadata=PDCExtractionMetadata(
                url=f"{etl_config.PDC_SENTRY_BASE_URL}/hp_srv/services/mags/1/json/get_mags?hazard_id={self.extraction_metadata.extraction_args['hazard_id']}",
                type=PDCExtractionMetaDataType.POLYGON,
                extraction_args={"hazard_id": self.extraction_metadata.extraction_args["hazard_id"]},
            ),
            parent_extraction=self.extraction_object.parent,
        )

        for item in response_data:
            exposure_extraction_obj = self.init_extraction(
                metadata=PDCExtractionMetadata(
                    url=f"{etl_config.PDC_SENTRY_BASE_URL}/hp_srv/services/hazard/{self.extraction_metadata.extraction_args['hazard_uuid']}/exposure/{item}",
                    type=PDCExtractionMetaDataType.EXPOSURE_DETAIL,
                    transform_args={
                        "exposure_id": item,
                        "hazard_uuid": self.extraction_metadata.extraction_args["hazard_uuid"],
                        "geojson_id": geo_json_obj.id,
                    },
                ),
                parent_extraction=self.extraction_object.parent,
                add_to_queue=False,
            )
            chord(
                [PDCExtractionV2.task.si(exposure_extraction_obj.id)],
                PDCTransformHandler.task.si(exposure_extraction_obj.id),
            ).apply_async()

    def handle_polygon(self):
        self._extraction_fetch_url(
            self.extraction_metadata.url,
        )

    def handle_exposure_detail(self):
        self._extraction_fetch_url(
            self.extraction_metadata.url,
            headers={
                "Authorization": f"Bearer {etl_config.PDC_SENTRY_AUTHORIZATION_KEY}",
                "Content-Type": "application/json",
            },
        )

    def handle_extract(self):
        handler_type = self.extraction_metadata.type
        logger.info(f"Starting extraction<{self.extraction_object.pk}> with metadata: {self.extraction_metadata}")
        match handler_type:
            case PDCExtractionMetaDataType.HAZARD:
                return self.handle_type_hazard()
            case PDCExtractionMetaDataType.EXPOSURE_LIST:
                return self.handle_exposure_list()
            case PDCExtractionMetaDataType.EXPOSURE_DETAIL:
                return self.handle_exposure_detail()
            case PDCExtractionMetaDataType.POLYGON:
                return self.handle_polygon()
            case _:
                typing.assert_never(handler_type)

    @staticmethod
    @app.task(
        bind=True,
        base=RetryableTask,
    )
    def task(celery_task, extraction_id):
        PDCExtractionV2(celery_task, extraction_id).handle()
