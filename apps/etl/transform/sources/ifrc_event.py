import json
import logging
import os
from pathlib import Path

from django.conf import settings
from pystac_monty.sources.common import DataType, File, GenericDataSource
from pystac_monty.sources.ifrc_events import IFRCEventDataSource, IFRCEventTransformer

from apps.etl.transform.sources.handler import BaseTransformerHandler
from apps.etl.utils import write_into_temp_file
from main.celery import CeleryQueue, app

logger = logging.getLogger(__name__)


class IFRCEventTransformHandler(BaseTransformerHandler[IFRCEventTransformer, IFRCEventDataSource]):
    transformer_class = IFRCEventTransformer
    transformer_schema = IFRCEventDataSource

    @classmethod
    def get_schema_data(cls, extraction_obj, dir_uuid: str):
        tmp_dir_path = Path("/tmp") / extraction_obj.get_source_display() / dir_uuid
        if not os.path.isdir(tmp_dir_path):
            os.makedirs(tmp_dir_path, exist_ok=True)

        with extraction_obj.resp_data.open() as file_data:
            data = json.loads(file_data.read())

        data_file = write_into_temp_file(json.dumps(data["results"]).encode("utf-8"), tmp_dir_path)
        data_source = GenericDataSource(
            source_url=extraction_obj.url, input_data=File(path=data_file.name, data_type=DataType.FILE)
        )

        result = cls.transformer_schema(data_source)

        return result

    @staticmethod
    @app.task(queue=CeleryQueue.TRANSFORM)
    def task(extraction_id):
        IFRCEventTransformHandler().handle_transformation(extraction_id, settings.IFRC_TRANSFORMER_VERSION)
