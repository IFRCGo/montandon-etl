from pystac_monty.sources.common import DataType, File, GenericDataSource
from pystac_monty.sources.idu import IDUDataSource, IDUTransformer

from apps.etl.transform.sources.handler import BaseTransformerHandler
from apps.etl.utils import write_into_temp_file
from main.celery import CeleryQueue, app


class IDUTransformHandler(BaseTransformerHandler[IDUTransformer, IDUDataSource]):
    transformer_class = IDUTransformer
    transformer_schema = IDUDataSource

    @classmethod
    def get_schema_data(cls, extraction_obj):
        with extraction_obj.resp_data.open("rb") as file_data:
            file_content = file_data.read()

        data_file = write_into_temp_file(content=file_content)

        data_source = GenericDataSource(
            source_url=extraction_obj.url, input_data=File(path=data_file.name, data_type=DataType.FILE)
        )

        result = cls.transformer_schema(data_source)

        tmp_files = [data_file]
        return result, tmp_files

    @staticmethod
    @app.task(queue=CeleryQueue.TRANSFORM)
    def task(extraction_id):
        IDUTransformHandler().handle_transformation(extraction_id)
