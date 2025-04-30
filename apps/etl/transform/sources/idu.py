from pystac_monty.sources.idu import IDUDataSource, IDUTransformer

from apps.etl.transform.sources.handler import BaseTransformerHandler
from main.celery import CeleryQueue, app


class IDUTransformHandler(BaseTransformerHandler[IDUTransformer, IDUDataSource]):
    transformer_class = IDUTransformer
    transformer_schema = IDUDataSource

    @classmethod
    def get_schema_data(cls, extraction_obj):
        with extraction_obj.resp_data.open() as file_data:
            data = file_data.read()

        return cls.transformer_schema(source_url=extraction_obj.url, data=data)

    @staticmethod
    @app.task(queue=CeleryQueue.DEFAULT)
    def task(extraction_id):
        IDUTransformHandler().handle_transformation(extraction_id)
