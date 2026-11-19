import logging
import os
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from pystac_monty.sources.common import DataType, File, Memory
from pystac_monty.sources.pdc import PDCDataSource, PDCDataSourceType, PDCTransformer

from apps.etl.models import ExtractionData, PyStacLoadData, Transform, get_trace_id
from apps.etl.utils import write_into_temp_file
from main.celery import CeleryQueue, app
from main.configs import etl_config

from .handler import BaseTransformerHandler

logger = logging.getLogger(__name__)


class PDCTransformHandler(BaseTransformerHandler[PDCTransformer, PDCDataSource]):
    """
    Transform runs once per hazard on the EXPOSURE_LIST extraction.

    All the extracted exposure details (snapshots) with distinct changes are passed to the
    transformer at once, so the event and hazard items are created only once along with the
    impact items for each snapshot.
    """

    transformer_class = PDCTransformer
    transformer_schema = PDCDataSource
    # NOTE: Exposure list/detail may not be available; transform using hazard data only in that case
    requires_resp_data = False

    @classmethod
    def get_exposure_list_extraction(cls, extraction_obj: ExtractionData) -> ExtractionData:
        """
        Transform is done on the EXPOSURE_LIST extraction.
        NOTE: EXPOSURE_DETAIL is resolved to its parent EXPOSURE_LIST (eg: retrigger of older transforms)
        """
        from apps.etl.extraction.sources.pdc.extract import PDCExtractionMetaDataType

        if (extraction_obj.metadata or {}).get("type") == PDCExtractionMetaDataType.EXPOSURE_DETAIL:
            return extraction_obj.parent
        return extraction_obj

    @classmethod
    def get_exposure_detail_extractions(cls, exposure_list_obj: ExtractionData) -> list[ExtractionData]:
        """Successful exposure details (snapshots) with distinct changes, latest snapshot first"""
        from apps.etl.extraction.sources.pdc.extract import PDCExtractionMetaDataType

        return list(
            ExtractionData.objects.filter(
                parent=exposure_list_obj,
                metadata__type=PDCExtractionMetaDataType.EXPOSURE_DETAIL,
                status=ExtractionData.Status.SUCCESS,
            )
            .exclude(source_validation_status=ExtractionData.ValidationStatus.NO_CHANGE)
            .exclude(resp_data="")
            .exclude(resp_data__isnull=True)
            .order_by("-id")
        )

    @classmethod
    def handle_transformation(cls, extraction_id: int, version: str):
        extraction_obj = cls.get_exposure_list_extraction(ExtractionData.objects.get(id=extraction_id))
        # NOTE: Remove the pending items of a previous transform of the same hazard (eg: retrigger)
        # so that the event and hazard items are not duplicated in the load table.
        PyStacLoadData.objects.filter(
            transform_id__in=Transform.objects.filter(extraction=extraction_obj, trace_id=get_trace_id(extraction_obj)),
            status=PyStacLoadData.Status.PENDING,
        ).delete()
        return super().handle_transformation(extraction_obj.pk, version)

    @classmethod
    def get_schema_data(cls, extraction_obj: ExtractionData, dir_uuid: str):
        tmp_dir_path = Path("/tmp") / extraction_obj.get_source_display() / dir_uuid
        if not os.path.isdir(tmp_dir_path):
            os.makedirs(tmp_dir_path, exist_ok=True)

        metadata: dict | None = extraction_obj.metadata
        if not metadata:
            raise Exception("Metadata is not defined")
        from apps.etl.extraction.sources.pdc.extract import (
            PDCExtractionMetadata,
            PDCExtractionMetaDataType,
        )

        input_metadata = PDCExtractionMetadata(**metadata)

        if input_metadata.type != PDCExtractionMetaDataType.EXPOSURE_LIST:
            raise Exception(f"PDC transform is only supported for EXPOSURE_LIST, got {input_metadata.type}")

        hazard_obj = extraction_obj.parent
        source_url = extraction_obj.url
        hazard_uuid = input_metadata.exposure_list.hazard_uuid  # type: ignore[union-attr]
        geojson_id = input_metadata.exposure_list.geo_obj_id  # type: ignore[union-attr]

        geo_json_obj = ExtractionData.objects.filter(id=geojson_id, status=ExtractionData.Status.SUCCESS).first()

        if not geo_json_obj:
            raise ObjectDoesNotExist("Geolocation object not found. It might not be extracted.")

        with hazard_obj.resp_data.open("rb") as f:
            file_content = f.read()
        # FIXME: Why do we have delete=False? We need to delete this in post action
        tmp_hazard_file = write_into_temp_file(file_content, tmp_dir_path)

        exposure_detail_data: list[File | Memory] = []
        for exposure_detail_obj in cls.get_exposure_detail_extractions(extraction_obj):
            with exposure_detail_obj.resp_data.open("rb") as f:
                file_content = f.read()
            # FIXME: Why do we have delete=False? We need to delete this in post action
            tmp_exposure_detail_file = write_into_temp_file(file_content, tmp_dir_path)
            exposure_detail_data.append(File(path=tmp_exposure_detail_file.name, data_type=DataType.FILE))

        if not exposure_detail_data:
            logger.warning(
                "Exposure detail data not available, transforming without exposure detail",
                extra={"extraction_id": extraction_obj.id},
            )

        result = cls.transformer_schema(
            data=PDCDataSourceType(
                source_url=source_url,
                uuid=hazard_uuid,
                hazard_data=File(path=tmp_hazard_file.name, data_type=DataType.FILE),
                exposure_detail_data=exposure_detail_data,
                geojson_path=geo_json_obj.resp_data.url,
            ),
            eoapi_url=etl_config.EOAPI_STAC_API_PUBLIC,
        )

        return result

    @staticmethod
    @app.task(queue=CeleryQueue.TRANSFORM)
    def task(extraction_id):
        return PDCTransformHandler().handle_transformation(extraction_id, settings.PDC_TRANSFORMER_VERSION)
