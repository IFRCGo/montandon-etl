from pystac_monty.sources.gfd import GFDDataSource, GFDTransformer

from apps.etl.models import ExtractionData
from apps.etl.transform.sources.handler import BaseTransformerHandler
from main.celery import app


class GFDTransformHandler(BaseTransformerHandler):
    transformer = GFDTransformer
    transformer_schema = GFDDataSource

    @classmethod
    def get_schema_data(cls, extraction_obj: ExtractionData):
        with extraction_obj.resp_data.open() as file_data:
            data = file_data.read()

        return cls.transformer_schema(source_url=extraction_obj.url, data=data)

    @staticmethod
    @app.task
    def task(extraction_id):
        return GFDTransformHandler().handle_transformation(extraction_id)
