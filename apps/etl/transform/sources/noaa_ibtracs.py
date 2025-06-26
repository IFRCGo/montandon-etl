import logging

from pystac_monty.sources.common import DataType, File, GenericDataSource
from pystac_monty.sources.ibtracs import IBTrACSDataSource, IBTrACSTransformer

from apps.etl.transform.sources.handler import BaseTransformerHandler
from apps.etl.utils import write_into_temp_file
from main.celery import app

logger = logging.getLogger(__name__)


class IbtracsTransformHandler(BaseTransformerHandler[IBTrACSTransformer, IBTrACSDataSource]):
    transformer_class = IBTrACSTransformer
    transformer_schema = IBTrACSDataSource

    @classmethod
    def get_schema_data(cls, extraction_obj):
        with extraction_obj.resp_data.open() as file_data:
            data = file_data.read()
        data_file = write_into_temp_file(data)

        data_source = GenericDataSource(
            source_url=extraction_obj.url,
            input_data=File(path=data_file.name, data_type=DataType.FILE),
        )

        result = cls.transformer_schema(data=data_source)

        tmp_files = [data_file]
        return result, tmp_files

    @staticmethod
    @app.task
    def task(extraction_id):
        IbtracsTransformHandler().handle_transformation(extraction_id)
