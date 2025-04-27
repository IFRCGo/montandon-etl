import json
import logging
import typing
from enum import Enum

import pydantic
import requests
from celery import chord
from django.core.files.base import ContentFile

from apps.etl.extraction.sources.base.handler import BaseExtraction, BaseExtractionV2
from apps.etl.models import ExtractionData, HazardType
from apps.etl.transform.sources.pdc import PDCTransformHandler
from apps.etl.utils import AccessTokenManager
from main.celery import app
from main.configs import etl_config
from main.logging import log_extra
from utils.celery import RetryableTask

logger = logging.getLogger(__name__)


class PDCExtractionMetaDataType(str, Enum):
    POLYGON = "polygon"
    EXPOSURE_LIST = "exposure_list"
    EXPOSURE_DETAIL = "exposure_detail"
    HAZARD = "hazard"


class PDCExtractionMetadata(pydantic.BaseModel):
    data: typing.Optional[dict] | None = None
    url: str
    type: PDCExtractionMetaDataType


class HazardEvent(pydantic.BaseModel):
    app_ID: int
    app_IDs: str
    category_ID: str
    charter_Uri: str
    comment_Text: typing.Optional[str]
    create_Date: str
    end_Date: str
    glide_Uri: str
    hazard_ID: int
    hazard_Name: str
    last_Update: str
    latitude: float
    longitude: float
    snc_url: str
    start_Date: str
    status: str
    type_ID: str
    uuid: str
    in_Dashboard: str
    description: str


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


class PDCExtraction(BaseExtraction):
    @staticmethod
    def fetch_geo_json(hazard_uuid: str):
        geo = AccessTokenManager(requests.Session())
        return geo.get_polygon(hazard_uuid)

    @staticmethod
    def fetch_exposure_data(hazard_uuid: str):
        url = f"{etl_config.PDC_SENTRY_BASE_URL}/hp_srv/services/hazard/{hazard_uuid}/exposure"
        headers = {"Authorization": f"Bearer {etl_config.PDC_SENTRY_AUTHORIZATION_KEY}"}
        return (requests.get(url, headers=headers).json(), url)

    @staticmethod
    def fetch_exposure_detail(hazard_uuid: str, exposure_id: int):
        url = f"{etl_config.PDC_SENTRY_BASE_URL}/hp_srv/services/hazard/{hazard_uuid}/exposure/{exposure_id}"
        headers = {"Authorization": f"Bearer {etl_config.PDC_SENTRY_AUTHORIZATION_KEY}"}
        return (requests.get(url, headers=headers).json(), url)

    @classmethod
    def store_pdc_data(
        cls,
        response,
        source: ExtractionData.Source,
        url: str,
        validate_source_func: typing.Any | None = None,
        # FIXME: intance_id is always None. This is a bug.
        instance_id: typing.Any | None = None,
        parent: ExtractionData | None = None,
        hazard_type: HazardType | None = None,
        metadata: typing.Any | None = None,
    ):
        file_name = f"{instance_id}pdc.json"
        data = json.dumps(response).encode("utf-8")
        instance = cls._create_extraction_instance(
            url="",
            source=source,
            parent_id=parent and parent.id,
            status=ExtractionData.Status.SUCCESS,
            hazard_type=hazard_type,
            metadata=metadata,
        )

        content_file = ContentFile(data)
        content_file.name = file_name
        instance.resp_data.save(content_file.name, content_file)

        return instance

    @classmethod
    # FIXME: Write pydantic type for hazard
    def process_hazard(cls, instance: ExtractionData, hazard: dict):
        try:
            if hazard["type_ID"] not in HAZARD_TYPE_MAP.keys():
                logger.warning(
                    "Skipping extraction because hazard is not supported",
                    extra=log_extra(
                        dict(
                            extraction_id=instance.id,
                            hazard_uuid=hazard["type_ID"],
                        )
                    ),
                )
                return

            hazard_uuid = hazard["uuid"]
            hazard_type_id = hazard["type_ID"]

            geo_json_file, geo_json_url = cls.fetch_geo_json(hazard_uuid)
            geo_json_data = cls.store_pdc_data(
                response=geo_json_file,
                source=ExtractionData.Source.PDC,
                url=geo_json_url,
                validate_source_func=None,
                parent=instance,
                hazard_type=HAZARD_TYPE_MAP.get(hazard_type_id),
                metadata={
                    "input": PdcPolygonInputMetadata(
                        hazard_uuid=hazard_uuid,
                        hazard_type_id=hazard_type_id,
                    ).model_dump(),
                },
            )

            exposure_ids, exposure_url = cls.fetch_exposure_data(hazard_uuid)
            if not len(exposure_ids):
                logger.warning(
                    "Skipping extraction because hazard is not supported",
                    extra=log_extra(
                        dict(
                            extraction_id=instance.id,
                            hazard_uuid=hazard_uuid,
                        )
                    ),
                )
                return

            for exposure_id in exposure_ids:
                if ExtractionData.objects.filter(
                    source=ExtractionData.Source.PDC,
                    status=ExtractionData.Status.SUCCESS,
                    metadata__input__exposure_id=exposure_id,
                    metadata__input__hazard_uuid=hazard_uuid,
                ).exists():
                    logger.info(
                        "Skipping extraction for parent extraction because exposure is already processed.",
                        extra=log_extra(
                            dict(
                                parent_extraction_id=instance.id,
                                exposure_id=exposure_id,
                                hazard_uuid=hazard_uuid,
                            )
                        ),
                    )
                    continue

                # FIXME: Need to run a separate extraction
                details, details_url = cls.fetch_exposure_detail(hazard_uuid, exposure_id)
                exposure_detail = cls.store_pdc_data(
                    response=details,
                    source=ExtractionData.Source.PDC,
                    validate_source_func=None,
                    url=details_url,
                    parent=instance,
                    hazard_type=HAZARD_TYPE_MAP.get(hazard["type_ID"]),
                    metadata={
                        "input": PdcExposureInputMetadata(
                            exposure_id=exposure_id,
                            hazard_uuid=hazard_uuid,
                            # FIXME: This is note exactly the input for pdc exposure
                            geojson_id=geo_json_data.id,
                        ).model_dump(),
                    },
                )
                PDCTransformHandler.task.delay(exposure_detail.id)
        except Exception as exc:
            logger.error("Error processing PDC data", extra=log_extra(dict(extraction_id=instance.id, error=str(exc))))
            raise exc

    @classmethod
    def handle_extraction(cls, params: dict, timeout: int = 30) -> None:
        """
        Process PDC data extraction.
        Returns:
            int: ID of the extraction instance
        """
        logger.info("Starting PDC data extraction")

        source = ExtractionData.Source.PDC
        url = f"{etl_config.PDC_SENTRY_BASE_URL}/hp_srv/services/hazards/t/json/search_hazard"
        headers = {
            "Authorization": f"Bearer {etl_config.PDC_SENTRY_AUTHORIZATION_KEY}",
            "Content-Type": "application/json",
        }
        page = params["pagination"]["page"]
        while True:
            instance = cls._create_extraction_instance(url=url, source=source)
            try:
                logger.info(
                    f"Extracting page {page}",
                    extra=log_extra(
                        {
                            "source": instance.source,
                            "page": params["pagination"]["page"],
                        }
                    ),
                )

                cls._update_instance_status(instance, ExtractionData.Status.IN_PROGRESS)

                response = requests.post(url, headers=headers, data=json.dumps(params), timeout=timeout)
                response.raise_for_status()

                instance.resp_code = response.status_code
                instance.metadata = params
                instance.save(update_fields=["resp_code", "metadata"])

                response_data = cls._save_response_data(instance, response)

                if response_data:
                    cls._update_instance_status(instance, ExtractionData.Status.SUCCESS)
                    logger.info(
                        "Data extracted successfully",
                        extra=log_extra(
                            {
                                "extraction_id": instance.id,
                                "hazard_count": len(response_data),
                            }
                        ),
                    )

                    for hazard in response_data:
                        cls.process_hazard(instance, hazard)
                else:
                    cls._update_instance_status(
                        instance,
                        ExtractionData.Status.SUCCESS,
                        ExtractionData.ValidationStatus.NO_DATA,
                        update_validation=True,
                    )
                    logger.warning(
                        "No hazard data found in response",
                        extra=log_extra(
                            {
                                "extraction_id": instance.id,
                            }
                        ),
                    )
                    break  # no data, stop paginating

                # Go to next page
                page += 1
                params["pagination"]["page"] = page

            except requests.exceptions.RequestException as e:
                cls._update_instance_status(instance, ExtractionData.Status.FAILED)
                logger.error(
                    "Extraction failed due to request error",
                    exc_info=True,
                    extra=log_extra(
                        {
                            "extraction_id": instance.id,
                            "error": str(e),
                        }
                    ),
                )
                raise


class PDCExtractionV2(BaseExtractionV2[PDCExtractionMetadata]):
    """
    PDC Extraction task.
    """

    source_enum = ExtractionData.Source.PDC
    extraction_metadata_class = PDCExtractionMetadata

    def handle_type_hazard(self):
        self._extraction_fetch_url(
            self.extraction_metadata.url,
            data=json.dumps(self.extraction_metadata.data),
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
                    data={"hazard_uuid": item["uuid"], "hazard_id": item["hazard_ID"]},
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
        response_data = json.loads(self.extraction_object.resp_data.read())

        self.init_extraction(
            metadata=PDCExtractionMetadata(
                url=f"{etl_config.PDC_SENTRY_BASE_URL}/hp_srv/services/mags/1/json/get_mags?hazard_id={self.extraction_metadata.data['hazard_id']}",
                type=PDCExtractionMetaDataType.POLYGON,
                data={"hazard_id": self.extraction_metadata.data["hazard_id"]},
            ),
            parent_extraction=self.extraction_object,
        )

        exposure_task = []
        for item in response_data:
            exposure_extraction_obj = self.init_extraction(
                metadata=PDCExtractionMetadata(
                    url=f"{etl_config.PDC_SENTRY_BASE_URL}/hp_srv/services/hazard/{self.extraction_metadata.data['hazard_uuid']}/exposure/{item}",
                    type=PDCExtractionMetaDataType.EXPOSURE_DETAIL,
                ),
                parent_extraction=self.extraction_object.parent.id,
                add_to_queue=False,
            )
            exposure_task.append(PDCExtractionV2.task.si(exposure_extraction_obj.pk))
        if exposure_task:
            chord(
                exposure_task,
                PDCTransformHandler.task.si(self.extraction_object.pk),
            ).apply_async()
        else:
            PDCTransformHandler.task.delay(self.extraction_object.pk)

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
