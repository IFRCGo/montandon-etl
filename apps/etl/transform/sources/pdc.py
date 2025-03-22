import json
import logging
import tempfile

from django.conf import settings
from pystac_monty.geocoding import GAULGeocoder
from pystac_monty.sources.pdc import PDCDataSource, PDCTransformer

from apps.etl.models import ExtractionData, Transform, get_trace_id
from main.celery import app
from main.logging import log_extra

from .handler import BaseTransformerHandler

logger = logging.getLogger(__name__)


class PDCTransformHandler(BaseTransformerHandler):
    transformer = PDCTransformer
    transformer_schema = PDCDataSource

    @classmethod
    def get_schema_data(cls, extraction_obj: ExtractionData, geo_json_obj: ExtractionData):  # type: ignore[reportIncompatibleMethodOverride]
        source_url = extraction_obj.url

        with extraction_obj.parent.resp_data.open("rb") as f:
            file_content = f.read()
        tmp_hazard_file = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        tmp_hazard_file.write(file_content)

        with extraction_obj.resp_data.open("rb") as f:
            file_content = f.read()
        tmp_exposure_detail_file = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        tmp_exposure_detail_file.write(file_content)

        with geo_json_obj.resp_data.open("rb") as f:
            file_content = f.read()
        tmp_geojson_file = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        tmp_geojson_file.write(file_content)

        data = {
            "hazards_file_path": tmp_hazard_file.name,
            "exposure_timestamp": extraction_obj.metadata["exposure_id"],
            "uuid": extraction_obj.metadata["uuid"],
            "exposure_detail_file_path": tmp_exposure_detail_file.name,
            "geojson_file_path": tmp_geojson_file.name,
        }

        return cls.transformer_schema(source_url=source_url, data=json.dumps(data))

    @classmethod
    def handle_transformation(cls, extraction_id, geo_json_id):  # type: ignore[reportIncompatibleMethodOverride]
        logger.info("Transformation started")
        extraction_obj = ExtractionData.objects.get(id=extraction_id)
        geo_json_obj = ExtractionData.objects.get(id=geo_json_id)
        if not extraction_obj.resp_data:
            logger.info("Transformation ended due to no data")
            return

        transform_obj = Transform.objects.create(
            extraction=extraction_obj,
            status=Transform.Status.PENDING,
            trace_id=get_trace_id(extraction_obj),
        )

        geocoder = GAULGeocoder(gpkg_path=None, service_base_url=settings.GEOCODER_URL)

        try:
            schema = cls.get_schema_data(extraction_obj, geo_json_obj)
            transformer = cls.transformer(schema, geocoder)
            transformed_items = transformer.make_items()

            transform_obj.status = Transform.Status.SUCCESS
            transform_obj.save(update_fields=["status"])

            cls.load_stac_item_to_queue(transformed_items, transform_obj.id)

            logger.info("Transformation ended")

        except Exception as e:
            logger.error("Transformation failed", exc_info=True, extra=log_extra({"extraction_id": extraction_obj.id}))
            transform_obj.status = Transform.Status.FAILED
            transform_obj.save(update_fields=["status"])
            # FIXME: Check if this creates duplicate entry in Sentry. if yes, remove this.
            raise e

    @staticmethod
    @app.task
    def task(extraction_id, geo_json_id):  # type: ignore[reportIncompatibleMethodOverride]
        return PDCTransformHandler().handle_transformation(extraction_id, geo_json_id)
