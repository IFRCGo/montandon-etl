import os

from pystac_monty.sources.common import DataType, File, GenericDataSource
from pystac_monty.sources.gidd import GIDDDataSource, GIDDTransformer

from apps.etl.transform.sources.handler import BaseTransformerHandler
from apps.etl.utils import write_into_temp_file
from main.celery import CeleryQueue, app


class GIDDTransformHandler(BaseTransformerHandler[GIDDTransformer, GIDDDataSource]):
    transformer_class = GIDDTransformer
    transformer_schema = GIDDDataSource

    @classmethod
    def get_schema_data(cls, extraction_obj):
        with extraction_obj.resp_data.open() as file_data:
            file_content = file_data.read()

        data_file = write_into_temp_file(content=file_content)

        data_source = GenericDataSource(
            source_url=extraction_obj.url, input_data=File(path=data_file.name, data_type=DataType.FILE)
        )

        result = cls.transformer_schema(data_source)

        if os.path.exists(data_file.name):
            os.remove(data_file.name)
        return result

    @staticmethod
    @app.task(queue=CeleryQueue.DEFAULT)
    def task(extraction_id):
        GIDDTransformHandler().handle_transformation(extraction_id)
