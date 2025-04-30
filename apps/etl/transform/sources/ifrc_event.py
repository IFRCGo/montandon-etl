import json
import logging

from pystac_monty.sources.ifrc_events import IFRCEventDataSource, IFRCEventTransformer

from apps.etl.transform.sources.handler import BaseTransformerHandler
from main.celery import CeleryQueue, app

logger = logging.getLogger(__name__)


class IFRCEventTransformHandler(BaseTransformerHandler[IFRCEventTransformer, IFRCEventDataSource]):
    transformer_class = IFRCEventTransformer
    transformer_schema = IFRCEventDataSource

    @classmethod
    def get_schema_data(cls, extraction_obj):
        with extraction_obj.resp_data.open() as file_data:
            data = json.loads(file_data.read())
        return cls.transformer_schema(
            source_url=extraction_obj.url,
            data=json.dumps(data["results"]),
        )

    @staticmethod
    @app.task(queue=CeleryQueue.TRANSFORM)
    def task(extraction_id):
        IFRCEventTransformHandler().handle_transformation(extraction_id)
