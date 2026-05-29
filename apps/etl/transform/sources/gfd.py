import os
from pathlib import Path

from django.conf import settings
from pystac_monty.sources.common import DataType, File, GenericDataSource
from pystac_monty.sources.gfd import GFDDataSource, GFDTransformer

from apps.etl.models import ExtractionData
from apps.etl.transform.sources.handler import BaseTransformerHandler
from apps.etl.utils import write_into_temp_file
from main.celery import CeleryQueue, app
from main.configs import etl_config


class GFDTransformHandler(BaseTransformerHandler[GFDTransformer, GFDDataSource]):
    transformer_class = GFDTransformer
    transformer_schema = GFDDataSource

    @classmethod
    def get_schema_data(cls, extraction_obj: ExtractionData, dir_uuid: str):
        tmp_dir_path = Path("/tmp") / extraction_obj.get_source_display() / dir_uuid
        if not os.path.isdir(tmp_dir_path):
            os.makedirs(tmp_dir_path, exist_ok=True)

        with extraction_obj.resp_data.open("rb") as file_data:
            file_content = file_data.read()

        data_file = write_into_temp_file(file_content, tmp_dir_path)

        data_source = GenericDataSource(
            source_url=extraction_obj.url, input_data=File(path=data_file.name, data_type=DataType.FILE)
        )
        result = cls.transformer_schema(data=data_source, eoapi_url=etl_config.EOAPI_STAC_API_PUBLIC)
        return result

    @staticmethod
    @app.task(queue=CeleryQueue.TRANSFORM)
    def task(extraction_id):
        GFDTransformHandler().handle_transformation(extraction_id, settings.GFD_TRANSFORMER_VERSION)
