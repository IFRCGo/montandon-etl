from pystac_monty.sources.gidd import GIDDDataSource, GIDDTransformer

from apps.etl.transform.sources.handler import BaseTransformerHandler
from main.celery import CeleryQueue, app


class GIDDTransformHandler(BaseTransformerHandler[GIDDTransformer, GIDDDataSource]):
    transformer_class = GIDDTransformer
    transformer_schema = GIDDDataSource

    @classmethod
    def get_schema_data(cls, extraction_obj):
        with extraction_obj.resp_data.open() as file_data:
            data = file_data.read()

        return cls.transformer_schema(source_url=extraction_obj.url, data=data)

    @staticmethod
    @app.task(queue=CeleryQueue.DEFAULT)
    def task(extraction_id):
        GIDDTransformHandler().handle_transformation(extraction_id)
