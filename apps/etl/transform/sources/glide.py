import json
import os
from pathlib import Path

from django.conf import settings
from pystac_monty.sources.common import DataType, File, GenericDataSource
from pystac_monty.sources.glide import GlideDataSource, GlideTransformer

from apps.etl.models import ExtractionData
from apps.etl.transform.sources.handler import BaseTransformerHandler
from apps.etl.utils import write_into_temp_file
from main.celery import CeleryQueue, app


class GlideTransformHandler(BaseTransformerHandler[GlideTransformer, GlideDataSource]):
    transformer_class = GlideTransformer
    transformer_schema = GlideDataSource

    @classmethod
    def get_schema_data(cls, extraction_obj):
        tmp_dir_path = Path("/tmp") / extraction_obj.get_source_display() / str(extraction_obj.id)
        if not os.path.isdir(tmp_dir_path):
            os.makedirs(tmp_dir_path, exist_ok=True)

        with extraction_obj.resp_data.open("rb") as f:
            data = f.read()
        data_file = write_into_temp_file(data, tmp_dir_path)

        result = cls.transformer_schema(
            data=GenericDataSource(
                source_url=extraction_obj.url,
                input_data=File(path=data_file.name, data_type=DataType.FILE),
            )
        )
        return result

    @staticmethod
    @app.task(queue=CeleryQueue.TRANSFORM)
    def task(extraction_id):
        extraction_obj = ExtractionData.objects.get(id=extraction_id)
        with extraction_obj.resp_data.open() as file_data:
            data = file_data.read()

        if not json.loads(data)["glideset"]:
            return
        else:
            GlideTransformHandler().handle_transformation(extraction_id, settings.GLIDE_TRANSFORMER_VERSION)
