import logging

from django.conf import settings
from pystac_monty.sources.common import DataType, File, GenericDataSource
from pystac_monty.sources.emdat import EMDATDataSource, EMDATTransformer

from apps.etl.models import ExtractionData
from apps.etl.transform.sources.handler import BaseTransformerHandler
from apps.etl.utils import write_into_temp_file
from main.celery import CeleryQueue, app

logger = logging.getLogger(__name__)


class EMDATTransformHandler(BaseTransformerHandler[EMDATTransformer, EMDATDataSource]):
    transformer_class = EMDATTransformer
    transformer_schema = EMDATDataSource

    @classmethod
    def get_schema_data(cls, extraction_obj: ExtractionData):
        with extraction_obj.resp_data.open("rb") as f:
            data = f.read()
        data_file = write_into_temp_file(data)

        result = cls.transformer_schema(
            data=GenericDataSource(
                source_url=extraction_obj.url,
                input_data=File(path=data_file.name, data_type=DataType.FILE),
            )
        )

        tmp_files = [data_file]
        return result, tmp_files

    @staticmethod
    @app.task(queue=CeleryQueue.TRANSFORM)
    def task(extraction_id):
        EMDATTransformHandler().handle_transformation(extraction_id, settings.EMDAT_TRANSFORMER_VERSION)
