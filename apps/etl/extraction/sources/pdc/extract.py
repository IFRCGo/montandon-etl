import hashlib
import json
import logging
import time
import typing
from enum import Enum

import pydantic
from celery import chord, group

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
    hazard_uuid: str | None
    hazard_id: int | None
    exposure_obj_id: int | None


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
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36 IFRC GO",  # noqa
        }
        if headers:
            return {**default_headers, **headers}
        return default_headers

    def _find_existing_child(self, **metadata_filters) -> ExtractionData | None:
        return ExtractionData.objects.filter(parent=self.extraction_object, **metadata_filters).order_by("-id").first()

    def handle_type_hazard(self, retrigger: bool, failed_int: int | None):
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
        if response_data and len(response_data) == 100:
            next_page = self.extraction_metadata.hazard.pagination.page + 1
            next_page_extraction = self._find_existing_child(
                metadata__type=PDCExtractionMetaDataType.HAZARD,
                metadata__hazard__pagination__page=next_page,
            )
            if next_page_extraction is None:
                data = self.extraction_metadata.hazard.model_copy(deep=True)
                data.pagination.page = next_page

                self.init_extraction(
                    metadata=PDCExtractionMetadata(
                        hazard=data,
                        url=self.extraction_metadata.url,
                        type=PDCExtractionMetaDataType.HAZARD,
                    ),
                    parent_extraction=self.extraction_object,
                    queue_name=CeleryQueue.EXTRACTION,
                )

        geo_objects = []
        hazard_extraction_objects = []
        for item in response_data:
            geo_object = self._find_existing_child(
                metadata__type=PDCExtractionMetaDataType.POLYGON,
                metadata__polygon__hazard_uuid=item["uuid"],
            )
            if geo_object is None:
                geo_object = self.init_extraction(
                    metadata=PDCExtractionMetadata(
                        url=f"{etl_config.PDC_SENTRY_BASE_URL}/hp_srv/services/mags/1/json/get_mags?hazard_id={item['hazard_ID']}",
                        type=PDCExtractionMetaDataType.POLYGON,
                        polygon=PdcPolygonMetadata(
                            hazard_uuid=item["uuid"], hazard_id=item["hazard_ID"], exposure_obj_id=None
                        ),
                    ),
                    parent_extraction=self.extraction_object,
                    add_to_queue=False,
                )

            exposure_extraction_obj = self._find_existing_child(
                metadata__type=PDCExtractionMetaDataType.EXPOSURE_LIST,
                metadata__exposure_list__hazard_uuid=item["uuid"],
            )
            if exposure_extraction_obj is None:
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

            geo_object.metadata["polygon"]["exposure_obj_id"] = exposure_extraction_obj.id
            geo_object.save()

            if geo_object.status != ExtractionData.Status.SUCCESS:
                geo_objects.append(PDCExtractionV2.task.s(geo_object.pk))
            if exposure_extraction_obj.status != ExtractionData.Status.SUCCESS:
                hazard_extraction_objects.append(PDCExtractionV2.task.si(exposure_extraction_obj.pk))

        if hazard_extraction_objects:
            chord(geo_objects)(group(hazard_extraction_objects))

    def handle_exposure_list(self, retrigger: bool, failed_int: int | None):
        if self.extraction_object.status != ExtractionData.Status.SUCCESS:
            self._extraction_fetch_url(
                self.extraction_metadata.url,
                headers=self._get_request_headers(),
            )

        if not self.extraction_object.resp_data:
            raise NoDataException

        response_data = json.loads(self.extraction_object.resp_data.read())
        if not response_data:
            raise NoDataException

        all_pks: list[int] = []
        has_pending = False
        for item in response_data:
            exposure_extraction_obj = self._find_existing_child(
                metadata__type=PDCExtractionMetaDataType.EXPOSURE_DETAIL,
                metadata__exposure_detail__exposure_id=item,
            )
            if exposure_extraction_obj is None:
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
                    parent_extraction=self.extraction_object,
                    add_to_queue=False,
                )
                has_pending = True
            elif exposure_extraction_obj.status != ExtractionData.Status.SUCCESS:
                has_pending = True
            all_pks.append(exposure_extraction_obj.pk)

        if not has_pending:
            return

        batch_tasks = [
            PDCExposureBatchTask.task.si(all_pks[i : i + PDCExposureBatchTask.BATCH_SIZE])
            for i in range(0, len(all_pks), PDCExposureBatchTask.BATCH_SIZE)
        ]
        group(batch_tasks).apply_async()

    def handle_polygon(self):
        headers = dict(self._get_request_headers())
        for key in ("Content-Type", "Authorization"):
            headers.pop(key, None)

        self._extraction_fetch_url(self.extraction_metadata.url, headers=headers)

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
                return self.handle_type_hazard(retrigger=retrigger, failed_int=failed_int)
            case PDCExtractionMetaDataType.EXPOSURE_LIST:
                return self.handle_exposure_list(retrigger=retrigger, failed_int=failed_int)
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
            PDCExtractionV2.task.delay(extraction_object.parent.id, retrigger=True, failed_int=extraction_object.id)

    @staticmethod
    @app.task(
        bind=True,
        base=RetryableTask,
        queue=CeleryQueue.EXTRACTION,
    )
    def task(celery_task, extraction_id, retrigger: bool = False, failed_int: int | None = None):
        PDCExtractionV2(celery_task, extraction_id).handle(retrigger=retrigger, failed_int=failed_int)


class PDCExposureBatchTask:
    """
    Processes a batch of EXPOSURE_DETAIL extractions sequentially.

    Within each batch the impact data hash (excluding the timestamp field) is compared
    between consecutive extractions.  When the hash is unchanged the extraction is marked
    NO_CHANGE and the Transform step is skipped; otherwise Transform is queued as normal.
    Batches run in parallel via Celery group, but items within a batch are sequential so
    the comparison chain is maintained.
    """

    BATCH_SIZE = 100
    BATCH_ITEM_MAX_RETRIES = 3

    @staticmethod
    def compute_exposure_detail_hash(resp_data: bytes) -> str:
        data = json.loads(resp_data)
        data.pop("timestamp", None)
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

    def __init__(self, celery_task):
        self.celery_task = celery_task

    def handle(self, extraction_pks: list[int]):
        prev_hash: str | None = None
        prev_extraction_obj: ExtractionData | None = None

        for pk in extraction_pks:
            extraction_obj = ExtractionData.objects.get(pk=pk)

            # Already processed on a previous run — restore its hash for comparison continuity.
            if extraction_obj.status == ExtractionData.Status.SUCCESS:
                prev_hash = extraction_obj.file_hash
                prev_extraction_obj = extraction_obj
                continue

            fetcher = PDCExtractionV2(self.celery_task, pk)
            extraction_obj = fetcher.extraction_object
            extraction_obj.mark_as_started()

            for attempt in range(PDCExposureBatchTask.BATCH_ITEM_MAX_RETRIES + 1):
                try:
                    fetcher.handle_exposure_detail()
                    break
                except Exception:
                    if attempt < PDCExposureBatchTask.BATCH_ITEM_MAX_RETRIES:
                        delay = RetryableTask.exponential_backoff_with_jitter(attempt)
                        logger.warning(
                            "ExposureDetail %s: attempt %d/%d failed, retrying in %.1fs",
                            pk,
                            attempt + 1,
                            PDCExposureBatchTask.BATCH_ITEM_MAX_RETRIES + 1,
                            delay,
                            extra=log_extra({"source": ExtractionData.Source.PDC}),
                        )
                        time.sleep(delay)
                    else:
                        logger.exception(
                            "ExposureDetail %s failed after %d attempts, preserving hash chain",
                            pk,
                            PDCExposureBatchTask.BATCH_ITEM_MAX_RETRIES + 1,
                            extra=log_extra({"source": ExtractionData.Source.PDC}),
                        )
                        extraction_obj.mark_as_ended(ExtractionData.Status.FAILED)
            else:
                # All retries exhausted — skip to next item, keep prev_hash/prev_extraction_obj
                # intact so the next successful item still compares against the last known state.
                continue

            extraction_obj.mark_as_ended(ExtractionData.Status.SUCCESS)

            if not extraction_obj.resp_data:
                prev_hash = None
                prev_extraction_obj = None
                continue

            with extraction_obj.resp_data.open("rb") as f:
                current_hash = PDCExposureBatchTask.compute_exposure_detail_hash(f.read())

            extraction_obj.file_hash = current_hash
            if prev_hash is not None and current_hash == prev_hash:
                extraction_obj.revision_id = prev_extraction_obj
                extraction_obj.source_validation_status = ExtractionData.ValidationStatus.NO_CHANGE
                extraction_obj.save(update_fields=["file_hash", "source_validation_status", "revision_id_id"])
                logger.info("ExposureDetail %s: data unchanged, skipping transform", pk)
            else:
                extraction_obj.save(update_fields=["file_hash"])
                PDCTransformHandler.task.delay(pk)

            prev_extraction_obj = extraction_obj
            prev_hash = current_hash

    @staticmethod
    @app.task(
        bind=True,
        base=RetryableTask,
        queue=CeleryQueue.EXTRACTION,
        name="apps.etl.extraction.sources.pdc.extract.PDCExposureBatchTask.task",
    )
    def task(celery_task, extraction_pks: list[int]):
        PDCExposureBatchTask(celery_task).handle(extraction_pks)
