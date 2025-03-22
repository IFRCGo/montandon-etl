import logging

from pystac_monty.sources.ifrc_events import IFRCEventDataSource, IFRCEventTransformer

from apps.etl.models import ExtractionData
from apps.etl.transform.sources.handler import BaseTransformerHandler
from main.celery import app

logger = logging.getLogger(__name__)


class IFRCEventTransformHandler(BaseTransformerHandler):
    transformer_class = IFRCEventTransformer
    transformer_schema = IFRCEventDataSource

    @classmethod
    def get_schema_data(cls, extraction_obj: ExtractionData):
        with extraction_obj.resp_data.open() as file_data:
            data = file_data.read()

        return cls.transformer_schema(
            source_url=extraction_obj.url,
            data=data,
        )

    @staticmethod
    @app.task
    def task(extraction_id):
        return IFRCEventTransformHandler().handle_transformation(extraction_id)
