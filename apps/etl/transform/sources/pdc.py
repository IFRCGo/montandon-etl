import logging
import os
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from pystac_monty.sources.common import DataType, File
from pystac_monty.sources.pdc import PDCDataSource, PDCDataSourceType, PDCTransformer

from apps.etl.models import ExtractionData
from apps.etl.utils import write_into_temp_file
from main.celery import CeleryQueue, app
from main.configs import etl_config

from .handler import BaseTransformerHandler

logger = logging.getLogger(__name__)


class PDCTransformHandler(BaseTransformerHandler[PDCTransformer, PDCDataSource]):
    transformer_class = PDCTransformer
    transformer_schema = PDCDataSource
    # NOTE: Exposure list/detail may not be available; transform using hazard data only in that case
    requires_resp_data = False

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

        if input_metadata.type == PDCExtractionMetaDataType.EXPOSURE_LIST:
            # NOTE: Exposure list is not available; transform without exposure detail
            hazard_obj = extraction_obj.parent
            source_url = extraction_obj.url
            hazard_uuid = input_metadata.exposure_list.hazard_uuid  # type: ignore[union-attr]
            geojson_id = input_metadata.exposure_list.geo_obj_id  # type: ignore[union-attr]
            exposure_resp_data = None
        else:
            hazard_obj = extraction_obj.parent.parent
            source_url = extraction_obj.parent.url
            hazard_uuid = input_metadata.exposure_detail.hazard_uuid  # type: ignore[union-attr]
            geojson_id = input_metadata.exposure_detail.geojson_id  # type: ignore[union-attr]
            exposure_resp_data = extraction_obj.resp_data

        geo_json_obj = ExtractionData.objects.filter(id=geojson_id, status=ExtractionData.Status.SUCCESS).first()

        if not geo_json_obj:
            raise ObjectDoesNotExist("Geolocation object not found. It might not be extracted.")

        with hazard_obj.resp_data.open("rb") as f:
            file_content = f.read()
        # FIXME: Why do we have delete=False? We need to delete this in post action
        tmp_hazard_file = write_into_temp_file(file_content, tmp_dir_path)

        exposure_detail_data: File | None = None
        if exposure_resp_data:
            with exposure_resp_data.open("rb") as f:
                file_content = f.read()
            # FIXME: Why do we have delete=False? We need to delete this in post action
            tmp_exposure_detail_file = write_into_temp_file(file_content, tmp_dir_path)
            exposure_detail_data = File(path=tmp_exposure_detail_file.name, data_type=DataType.FILE)
        else:
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
