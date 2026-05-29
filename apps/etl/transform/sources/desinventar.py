import logging
import os
import tempfile
import uuid
from pathlib import Path

from django.conf import settings
from pystac_monty.geocoding import TheirGeocoder
from pystac_monty.sources.common import DataType, DesinventarDataSourceType, File
from pystac_monty.sources.desinventar import (
    DesinventarDataSource,
    DesinventarTransformer,
)

from apps.etl.models import ExtractionData, Transform, get_trace_id
from apps.etl.transform.sources.handler import BaseTransformerHandler
from apps.etl.utils import remove_tmp_directory
from main.celery import CeleryQueue, app
from main.configs import etl_config
from main.logging import log_extra

logger = logging.getLogger(__name__)


class DesinventarTransformHandler(BaseTransformerHandler[DesinventarTransformer, DesinventarDataSource]):
    transformer_class = DesinventarTransformer
    transformer_schema = DesinventarDataSource

    @classmethod
    def get_schema_data(cls, extraction_obj: ExtractionData, country_code: str, iso3: str, dir_uuid: str):  # type: ignore[reportIncompatibleMethodOverride]
        tmp_dir_path = Path("/tmp") / extraction_obj.get_source_display() / dir_uuid
        if not os.path.isdir(tmp_dir_path):
            os.makedirs(tmp_dir_path, exist_ok=True)

        with extraction_obj.resp_data.open("rb") as f:
            file_content = f.read()

        tmp_zip_file = tempfile.NamedTemporaryFile(dir=tmp_dir_path, suffix=".zip", delete=False)
        tmp_zip_file.write(file_content)

        data_source = DesinventarDataSourceType(
            tmp_zip_file=File(path=tmp_zip_file, data_type=DataType.FILE),
            source_url=f"{settings.DESINVENTAR_DATA_URL}/DesInventar/download/DI_export_{country_code}.zip",
            iso3=iso3,
            country_code=country_code,
        )
        result = cls.transformer_schema(data=data_source, eoapi_url=etl_config.EOAPI_STAC_API_PUBLIC)

        return result

    @classmethod
    def handle_transformation(cls, extraction_id: int, version: str):  # type: ignore[reportIncompatibleMethodOverride]
        logger.info("Transformation started")
        extraction_obj = ExtractionData.objects.get(id=extraction_id)
        from apps.etl.extraction.sources.desinventar.extract import DesInventarExtractionMetadata

        metadata = DesInventarExtractionMetadata(**extraction_obj.metadata)

        if not extraction_obj.resp_data:
            logger.info("Transformation ended because there is no data")
            return

        transform_obj, _ = Transform.objects.get_or_create(
            extraction=extraction_obj,
            trace_id=get_trace_id(extraction_obj),
            version=version,
        )

        transform_obj.mark_as_started()
        geocoder = TheirGeocoder(etl_config.GEOCODER_URL)
        dir_uuid = str(uuid.uuid4())

        try:
            schema = cls.get_schema_data(extraction_obj, metadata.params.country_code, metadata.params.iso3, dir_uuid)
            transformer = cls.transformer_class(schema, geocoder)
            transformed_items = transformer.get_stac_items()

            cls.load_stac_item_to_queue(transform_obj, transformed_items)

            summary = transformer.transform_summary
            transform_obj.metadata["summary"] = {
                "failed_rows": summary.failed_rows,
                "total_rows": summary.total_rows,
            }
            transform_obj.mark_as_ended(Transform.Status.SUCCESS, update_fields=["metadata"])
            logger.info("Transformation ended")
            remove_tmp_directory(extraction_obj, dir_uuid)

        except Exception as e:
            logger.error("Transformation failed", exc_info=True, extra=log_extra({"extraction_id": extraction_obj.id}))
            transform_obj.mark_as_ended(Transform.Status.FAILED)
            remove_tmp_directory(extraction_obj, dir_uuid)
            raise e

    @staticmethod
    @app.task(queue=CeleryQueue.TRANSFORM)
    def task(extraction_id: int):  # type: ignore[reportIncompatibleMethodOverride]
        DesinventarTransformHandler().handle_transformation(extraction_id, settings.DESINVENTAR_TRANSFROMER_VERSION)
