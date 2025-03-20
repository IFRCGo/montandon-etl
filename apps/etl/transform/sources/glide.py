from pystac_monty.sources.glide import GlideDataSource, GlideTransformer

from apps.etl.models import ExtractionData
from apps.etl.transform.sources.handler import BaseTransformerHandler
from main.celery import app


class GlideTransformHandler(BaseTransformerHandler):
    transformer = GlideTransformer
    transformer_schema = GlideDataSource

    @classmethod
    def get_schema_data(cls, extraction_obj: ExtractionData):
        with extraction_obj.resp_data.open() as file_data:
            data = file_data.read()

        return cls.transformer_schema(source_url=extraction_obj.url, data=data)

    @staticmethod
    @app.task
    def task(extraction_id):
        return GlideTransformHandler().handle_transformation(extraction_id)
