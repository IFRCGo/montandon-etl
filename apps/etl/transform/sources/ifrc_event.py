import logging

from django.conf import settings
from pystac_monty.geocoding import GAULGeocoder
from pystac_monty.sources.ifrc_events import IFRCEventDataSource, IFRCEventTransformer

from apps.etl.models import ExtractionData, Transform
from apps.etl.transform.sources.handler import BaseTransformerHandler
from main.celery import app

logger = logging.getLogger(__name__)


class IFRCEventTransformHandler(BaseTransformerHandler):
    transformer = IFRCEventTransformer
    transformer_schema = IFRCEventDataSource
    geocoder = GAULGeocoder(gpkg_path=None, service_base_url=settings.GEOCODER_URL)

    @classmethod
    def get_schema_data(cls, extraction_obj: ExtractionData):
        with extraction_obj.resp_data.open() as file_data:
            data = file_data.read()

        return cls.transformer_schema(
            source_url=extraction_obj.url,
            data=data,
        )

    @classmethod
    def handle_transformation(cls, extraction_id):
        logger.info("Transformation started")
        extraction_obj = ExtractionData.objects.filter(id=extraction_id).first()
        if not extraction_obj.resp_data:
            logger.info("Transformation ended due to no data")
            return

        transform_obj = Transform.objects.create(
            extraction=extraction_obj,
            status=Transform.Status.PENDING,
        )

        try:
            schema = cls.get_schema_data(extraction_obj)
            transformer = cls.transformer(data=schema, geocoder=cls.geocoder)
            transformed_items = transformer.make_items()

            transform_obj.status = Transform.Status.SUCCESS
            transform_obj.save(update_fields=["status"])

            cls.load_stac_item_to_queue(transformed_items, transform_obj.id)

            logger.info("Transformation ended")

        except Exception as e:
            logger.error("Transformation failed", exc_info=True, extra={"extraction_id": extraction_obj.id})
            transform_obj.status = Transform.Status.FAILED
            transform_obj.save(update_fields=["status"])
            # FIXME: Check if this creates duplicate entry in Sentry. if yes, remove this.
            raise e

    @staticmethod
    @app.task
    def task(extraction_id):
        return IFRCEventTransformHandler().handle_transformation(extraction_id)
