import logging

from pystac_monty.sources.ibtracs import IBTrACSDataSource, IBTrACSTransformer

from apps.etl.models import ExtractionData
from apps.etl.transform.sources.handler import BaseTransformerHandler
from main.celery import app

logger = logging.getLogger(__name__)


class IbtracsTransformHandler(BaseTransformerHandler):
    transformer = IBTrACSTransformer
    transformer_schema = IBTrACSDataSource

    @classmethod
    def get_schema_data(cls, extraction_obj: ExtractionData):
        with extraction_obj.resp_data.open() as file_data:
            data = file_data.read()

        return cls.transformer_schema(source_url=extraction_obj.url, data=data.decode("utf-8"))

    @staticmethod
    @app.task
    def task(extraction_id):
        return IbtracsTransformHandler().handle_transformation(extraction_id)
