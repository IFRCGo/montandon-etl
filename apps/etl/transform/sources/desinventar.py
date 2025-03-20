import logging
import tempfile

from pystac_monty.sources.desinventar import (
    DesinventarDataSource,
    DesinventarTransformer,
)

from apps.etl.models import ExtractionData, Transform
from apps.etl.transform.sources.handler import BaseTransformerHandler
from main.celery import app
from main.logging import log_extra

logger = logging.getLogger(__name__)


class DesinventarTransformHandler(BaseTransformerHandler):
    transformer = DesinventarTransformer
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
            status=Transform.Status.PENDING,
            trace_id=extraction_obj.trace_id,
        )

        try:
            schema = cls.get_schema_data(extraction_obj, country_code, iso3)
            transformer = cls.transformer(data_source=schema)
            transformed_items = transformer.get_items()

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

    # FIXME: Get country_code and iso3 from ExtractionData.metadata and remove parameters
    @staticmethod
    @app.task
    def task(extraction_id: int, country_code: str, iso3: str):  # type: ignore[reportIncompatibleMethodOverride]
        return DesinventarTransformHandler().handle_transformation(extraction_id, country_code, iso3)
