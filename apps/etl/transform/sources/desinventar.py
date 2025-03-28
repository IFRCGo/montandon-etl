import logging
import tempfile

from pystac_monty.geocoding import TheirGeocoder
from pystac_monty.sources.desinventar import (
    DesinventarDataSource,
    DesinventarTransformer,
)

from apps.etl.models import ExtractionData, Transform, get_trace_id
from apps.etl.transform.sources.handler import BaseTransformerHandler
from main.celery import app
from main.configs import etl_config
from main.logging import log_extra

logger = logging.getLogger(__name__)


class DesinventarTransformHandler(BaseTransformerHandler[DesinventarTransformer, DesinventarDataSource]):
    transformer_class = DesinventarTransformer
    transformer_schema = DesinventarDataSource

    @classmethod
    def get_schema_data(cls, extraction_obj: ExtractionData, country_code: str, iso3: str):  # type: ignore[reportIncompatibleMethodOverride]
        with extraction_obj.resp_data.open("rb") as f:
            file_content = f.read()

        # FIXME: Why do we have delete=False? We need to delete this in post action
        tmp_zip_file = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
        tmp_zip_file.write(file_content)

        return cls.transformer_schema(
            tmp_zip_file=tmp_zip_file,
            source_url=f"https://www.desinventar.net/DesInventar/download/DI_export_{country_code}.zip",
            country_code=country_code,
            iso3=iso3,
        )

    # FIXME: Get country_code and iso3 from ExtractionData.metadata and remove method
    @classmethod
    def handle_transformation(cls, extraction_id: int, country_code: str, iso3: str):  # type: ignore[reportIncompatibleMethodOverride]
        logger.info("Transformation started")
        extraction_obj = ExtractionData.objects.get(id=extraction_id)

        if not extraction_obj.resp_data:
            logger.info("Transformation ended because there is no data")
            return

        transform_obj = Transform.objects.create(
            extraction=extraction_obj,
            trace_id=get_trace_id(extraction_obj),
        )

        transform_obj.mark_as_started()
        geocoder = TheirGeocoder(etl_config.GEOCODER_URL)

        try:
            schema = cls.get_schema_data(extraction_obj, country_code, iso3)
            transformer = cls.transformer_class(schema, geocoder)
            transformed_items = transformer.make_items()

            cls.load_stac_item_to_queue(transform_obj, transformed_items)

            summary = transformer.transform_summary
            transform_obj.metadata["summary"] = {
                "failed_rows": summary.failed_rows,
                "total_rows": summary.total_rows,
            }
            transform_obj.mark_as_ended(Transform.Status.SUCCESS, update_fields=["metadata"])
            logger.info("Transformation ended")
        except Exception as e:
            logger.error("Transformation failed", exc_info=True, extra=log_extra({"extraction_id": extraction_obj.id}))
            transform_obj.mark_as_ended(Transform.Status.FAILED)
            # FIXME: Check if this creates duplicate entry in Sentry. if yes, remove this.
            raise e

    # FIXME: Get country_code and iso3 from ExtractionData.metadata and remove parameters
    @staticmethod
    @app.task
    def task(extraction_id: int, country_code: str, iso3: str):  # type: ignore[reportIncompatibleMethodOverride]
        DesinventarTransformHandler().handle_transformation(extraction_id, country_code, iso3)
