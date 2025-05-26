from pystac_monty.sources.common import DataType, File
from pystac_monty.sources.gidd import GIDDDataSourceV2, GIDDTransformer

from apps.etl.transform.sources.handler import BaseTransformerHandler
from apps.etl.utils import write_into_temp_file
from main.celery import CeleryQueue, app


class GIDDTransformHandler(BaseTransformerHandler[GIDDTransformer, GIDDDataSourceV2]):
    transformer_class = GIDDTransformer
    transformer_schema = GIDDDataSourceV2

    @classmethod
    def get_schema_data(cls, extraction_obj):
        with extraction_obj.resp_data.open() as file_data:
            file_content = file_data.read()

        data_file = write_into_temp_file(content=file_content)

        data_source = {"source_url": extraction_obj.url, "source_data": File(path=data_file.name, data_type=DataType.FILE)}

        return cls.transformer_schema(data_source)

    @staticmethod
    @app.task(queue=CeleryQueue.DEFAULT)
    def task(extraction_id):
        GIDDTransformHandler().handle_transformation(extraction_id)
