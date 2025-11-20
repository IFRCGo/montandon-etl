import json
import logging
import typing
from enum import Enum

import pydantic
from celery import chain, chord, group

from apps.etl.extraction.sources.base.handler import BaseExtractionV2, NoDataException
from apps.etl.models import ExtractionData, HazardType
from apps.etl.transform.sources.pdc import PDCTransformHandler
from main.celery import CeleryQueue, app
from main.configs import etl_config
from main.logging import log_extra
from utils.celery import RetryableTask

logger = logging.getLogger(__name__)


class PDCExtractionMetaDataType(str, Enum):
    POLYGON = "POLYGON"
    EXPOSURE_LIST = "EXPOSURE_LIST"
    EXPOSURE_DETAIL = "EXPOSURE_DETAIL"
    HAZARD = "HAZARD"


class PdcPolygonMetadata(pydantic.BaseModel):
    hazard_id: int


class PdcExposureMetadata(pydantic.BaseModel):
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


class PDCExposurelistMetadata(pydantic.BaseModel):
    hazard_uuid: str | None
    hazard_id: int | None
    geo_obj_id: int | None


class PdcHazardMetadata(pydantic.BaseModel):
    hazard_id: int | None = None


class PDCExtractionMetadata(pydantic.BaseModel):
    url: str
    type: PDCExtractionMetaDataType
    exposure_detail: typing.Optional[PdcExposureMetadata] = None
    hazard: typing.Optional[PdcHazardInputMetadata] = None
    exposure_list: typing.Optional[PDCExposurelistMetadata] = None
    polygon: typing.Optional[PdcPolygonMetadata] = None

    @pydantic.model_validator(mode="after")
    def check_required_by_type(self) -> "PDCExtractionMetadata":
        if self.type == PDCExtractionMetaDataType.EXPOSURE_DETAIL and not self.exposure_detail:
            raise ValueError("exposure_detail is required when type is 'exposure'")
        if self.type == PDCExtractionMetaDataType.EXPOSURE_LIST and not self.exposure_list:
            raise ValueError("exposure_list is required when type is 'exposure_list'")
        if self.type == PDCExtractionMetaDataType.HAZARD and not self.hazard:
            raise ValueError("hazard is required when type is 'hazard'")
        if self.type == PDCExtractionMetaDataType.EXPOSURE_LIST and not self.exposure_list:
            raise ValueError("exposure_list is required when type is 'exposure_list'")
        if self.type == PDCExtractionMetaDataType.POLYGON and not self.polygon:
            raise ValueError("polygon is required when type is 'polygon'")
        return self


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
    DEFAULT_CELERY_QUEUE = CeleryQueue.EXTRACTION

    @classmethod
    def _get_request_headers(cls, headers: dict[str, typing.Any] | None = None) -> dict[str, str]:
        default_headers = {
            "Authorization": f"Bearer {etl_config.PDC_SENTRY_AUTHORIZATION_KEY}",
            "Content-Type": "application/json",
        }
        if headers:
            return {**default_headers, **headers}
        return default_headers

    def handle_type_hazard(self, retrigger: bool):
        extraction_status = self._extraction_fetch_url(
            self.extraction_metadata.url,
            data=json.dumps(self.extraction_metadata.hazard.model_dump()),  # type: ignore
            headers=self._get_request_headers(),
            method="post",
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
        response_data = json.loads(self.extraction_object.resp_data.read())
        if not retrigger:
            if response_data and len(response_data) == 100:
                data = self.extraction_metadata.hazard.model_copy(deep=True)
                data.pagination.page += 1

                self.init_extraction(
                    metadata=PDCExtractionMetadata(
                        hazard=data,
                        url=self.extraction_metadata.url,
                        type=PDCExtractionMetaDataType.HAZARD,
                    ),
                    queue_name=CeleryQueue.EXTRACTION,
                )

        geo_objects = []
        hazard_extraction_objects = []
        for item in response_data:
            if not retrigger:
                geo_object = self.init_extraction(
                    metadata=PDCExtractionMetadata(
                        url=f"{etl_config.PDC_SENTRY_BASE_URL}/hp_srv/services/mags/1/json/get_mags?hazard_id={item['hazard_ID']}",
                        type=PDCExtractionMetaDataType.POLYGON,
                        polygon=PdcPolygonMetadata(hazard_id=item["hazard_ID"]),
                    ),
                    parent_extraction=self.extraction_object,
                    add_to_queue=False,
                )
                geo_objects.append(PDCExtractionV2.task.s(geo_object.pk))

                exposure_extraction_obj = self.init_extraction(
                    metadata=PDCExtractionMetadata(
                        url=f"{etl_config.PDC_SENTRY_BASE_URL}/hp_srv/services/hazard/{item['uuid']}/exposure",
                        type=PDCExtractionMetaDataType.EXPOSURE_LIST,
                        exposure_list=PDCExposurelistMetadata(
                            hazard_uuid=item["uuid"], hazard_id=item["hazard_ID"], geo_obj_id=geo_object.id
                        ),
                    ),
                    parent_extraction=self.extraction_object,
                    add_to_queue=False,
                )
                hazard_extraction_objects.append(PDCExtractionV2.task.si(exposure_extraction_obj.pk))
            else:
                geo_object = ExtractionData.objects.filter(
                    metadata__url=f"{etl_config.PDC_SENTRY_BASE_URL}/hp_srv/services/mags/1/json/get_mags?hazard_id={item['hazard_ID']}",
                ).first()

                if not geo_object:
                    geo_object = self.init_extraction(
                        metadata=PDCExtractionMetadata(
                            url=f"{etl_config.PDC_SENTRY_BASE_URL}/hp_srv/services/mags/1/json/get_mags?hazard_id={item['hazard_ID']}",
                            type=PDCExtractionMetaDataType.POLYGON,
                            polygon=PdcPolygonMetadata(hazard_id=item["hazard_ID"]),
                        ),
                        parent_extraction=self.extraction_object,
                        add_to_queue=False,
                    )
                geo_objects.append(PDCExtractionV2.task.s(geo_object.pk))

                exposure_extraction_obj = ExtractionData.objects.filter(
                    metadata__url=f"{etl_config.PDC_SENTRY_BASE_URL}/hp_srv/services/hazard/{item['uuid']}/exposure",
                ).first()

                if not exposure_extraction_obj:
                    exposure_extraction_obj = self.init_extraction(
                        metadata=PDCExtractionMetadata(
                            url=f"{etl_config.PDC_SENTRY_BASE_URL}/hp_srv/services/hazard/{item['uuid']}/exposure",
                            type=PDCExtractionMetaDataType.EXPOSURE_LIST,
                            exposure_list=PDCExposurelistMetadata(
                                hazard_uuid=item["uuid"], hazard_id=item["hazard_ID"], geo_obj_id=geo_object.id
                            ),
                        ),
                        parent_extraction=self.extraction_object,
                        add_to_queue=False,
                    )
                hazard_extraction_objects.append(PDCExtractionV2.task.si(exposure_extraction_obj.pk, retrigger=True))

        if hazard_extraction_objects:
            chord(geo_objects)(group(hazard_extraction_objects))

    def handle_exposure_list(self, retrigger: bool):
        self._extraction_fetch_url(
            self.extraction_metadata.url,
            headers=self._get_request_headers(),
        )

        if not self.extraction_object.resp_data:
            raise NoDataException

        response_data = json.loads(self.extraction_object.resp_data.read())
        if not response_data:
            raise NoDataException

        for item in response_data:
            if not retrigger:
                exposure_extraction_obj = self.init_extraction(
                    metadata=PDCExtractionMetadata(
                        url=f"{etl_config.PDC_SENTRY_BASE_URL}/hp_srv/services/hazard/{self.extraction_metadata.exposure_list.hazard_uuid}/exposure/{item}",  # type: ignore
                        type=PDCExtractionMetaDataType.EXPOSURE_DETAIL,
                        exposure_detail=PdcExposureMetadata(
                            exposure_id=item,
                            hazard_uuid=self.extraction_metadata.exposure_list.hazard_uuid,
                            geojson_id=self.extraction_metadata.exposure_list.geo_obj_id,
                        ),
                    ),
                    parent_extraction=self.extraction_object.parent,
                    add_to_queue=False,
                )
            else:
                exposure_extraction_obj = ExtractionData.objects.filter(
                    metadata__url=f"{etl_config.PDC_SENTRY_BASE_URL}/hp_srv/services/hazard/{self.extraction_metadata.exposure_list.hazard_uuid}/exposure/{item}",
                ).first()
                if not exposure_extraction_obj:
                    exposure_extraction_obj = self.init_extraction(
                        metadata=PDCExtractionMetadata(
                            url=f"{etl_config.PDC_SENTRY_BASE_URL}/hp_srv/services/hazard/{self.extraction_metadata.exposure_list.hazard_uuid}/exposure/{item}",  # type: ignore
                            type=PDCExtractionMetaDataType.EXPOSURE_DETAIL,
                            exposure_detail=PdcExposureMetadata(
                                exposure_id=item,
                                hazard_uuid=self.extraction_metadata.exposure_list.hazard_uuid,
                                geojson_id=self.extraction_metadata.exposure_list.geo_obj_id,
                            ),
                        ),
                        parent_extraction=self.extraction_object.parent,
                        add_to_queue=False,
                    )

            chord(
                PDCExtractionV2.task.si(exposure_extraction_obj.pk),
                PDCTransformHandler.task.si(exposure_extraction_obj.id),
            ).apply_async()

    def handle_polygon(self):
        self._extraction_fetch_url(
            self.extraction_metadata.url,
        )

    def handle_exposure_detail(self):
        self._extraction_fetch_url(
            self.extraction_metadata.url,
            headers=self._get_request_headers(),
        )

    @typing.override
    def handle_extract(self, retrigger: bool, failed_int: int | None = None):
        handler_type = self.extraction_metadata.type
        logger.info(f"Starting extraction<{self.extraction_object.pk}> with metadata: {self.extraction_metadata}")
        match handler_type:
            case PDCExtractionMetaDataType.HAZARD:
                return self.handle_type_hazard(retrigger=retrigger)
            case PDCExtractionMetaDataType.EXPOSURE_LIST:
                return self.handle_exposure_list(retrigger=retrigger)
            case PDCExtractionMetaDataType.EXPOSURE_DETAIL:
                return self.handle_exposure_detail()
            case PDCExtractionMetaDataType.POLYGON:
                return self.handle_polygon()
            case _:
                typing.assert_never(handler_type)

    def retrigger(extraction_object):
        metadata_type = extraction_object.metadata.get("type")
        if metadata_type == PDCExtractionMetaDataType.HAZARD:
            PDCExtractionV2.task.delay(extraction_object.id, retrigger=True, failed_int=extraction_object.id)
        if metadata_type == PDCExtractionMetaDataType.POLYGON:
            PDCExtractionV2.task.delay(extraction_object.parent.id, retrigger=True, failed_int=extraction_object.id)
        if metadata_type == PDCExtractionMetaDataType.EXPOSURE_LIST:
            PDCExtractionV2.task.delay(extraction_object.id, retrigger=True, failed_int=extraction_object.id)
        if metadata_type == PDCExtractionMetaDataType.EXPOSURE_DETAIL:
            chain(
                PDCExtractionV2.task.si(extraction_object.pk), PDCTransformHandler.task.si(extraction_object.id)
            ).apply_async()

    @staticmethod
    @app.task(
        bind=True,
        base=RetryableTask,
        queue=CeleryQueue.EXTRACTION,
    )
    def task(celery_task, extraction_id, retrigger: bool = False, failed_int: int | None = None):
        PDCExtractionV2(celery_task, extraction_id).handle(retrigger=retrigger, failed_int=failed_int)
