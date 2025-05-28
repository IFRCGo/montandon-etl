import json
import logging

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
    def get_schema_data(cls, extraction_obj):
        with extraction_obj.resp_data.open() as file_data:
            data = json.loads(file_data.read())

        data_file = write_into_temp_file(json.dumps(data["results"]).encode("utf-8"))

        data_source = IFRCEventDataSource(
            data=GenericDataSource(
                source_url=extraction_obj.url, data_source=File(path=data_file.name, data_type=DataType.FILE)
            )
        )
        return cls.transformer_schema(data_source)

    @staticmethod
    @app.task(queue=CeleryQueue.TRANSFORM)
    def task(extraction_id):
        IFRCEventTransformHandler().handle_transformation(extraction_id)
