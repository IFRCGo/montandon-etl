import logging
import os
from pathlib import Path

from django.conf import settings
from pystac_monty.sources.alerthub import AlertHubDataSource, AlertHubTransformer
from pystac_monty.sources.common import DataType, File, GenericDataSource

from apps.etl.models import ExtractionData
from apps.etl.transform.sources.handler import BaseTransformerHandler
from apps.etl.utils import write_into_temp_file
from main.celery import CeleryQueue, app

logger = logging.getLogger(__name__)


class AlertHubTransformHandler(BaseTransformerHandler[AlertHubTransformer, AlertHubDataSource]):
    transformer_class = AlertHubTransformer
    transformer_schema = AlertHubDataSource

    # NOTE: Changes to the base transformer be done.
    # dir_uuid is inappropriately overriding the get_schema_data?

    @classmethod
    def get_schema_data(cls, extraction_obj: ExtractionData, dir_uuid: str):
        tmp_dir_path = Path("/tmp") / extraction_obj.get_source_display() / dir_uuid
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
        AlertHubTransformHandler().handle_transformation(extraction_id, settings.ALERT_HUB_TRANSFORMER_VERSION)
