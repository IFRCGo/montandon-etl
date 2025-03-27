import json
import logging

from pystac_monty.sources.gdacs import (
    GDACSDataSource,
    GDACSDataSourceType,
    GDACSTransformer,
)

from apps.etl.transform.sources.handler import BaseTransformerHandler
from main.celery import app

logger = logging.getLogger(__name__)

# FIXME: start_end_handler base zzz


class GDACSTransformHandler(BaseTransformerHandler[GDACSTransformer, GDACSDataSource]):
    transformer_class = GDACSTransformer
    transformer_schema = GDACSDataSource

    @classmethod
    def get_schema_data(cls, extraction_object):
        data = extraction_object.resp_data.read()
        episodes = []
        event_objects = extraction_object.child_extractions.all()
        for episode_obj in event_objects:
            episodes_data_dict = {}
            event_episode_data = episode_obj.resp_data.read()
            episodes_data_dict[GDACSDataSourceType.EVENT] = (episode_obj.url, json.loads(event_episode_data))
            geometry_objects = episode_obj.child_extractions.all()

            for geometry_detail in geometry_objects:
                geometry_episode_data = geometry_detail.resp_data.read()
                episodes_data_dict[GDACSDataSourceType.GEOMETRY] = (geometry_detail.url, json.loads(geometry_episode_data))

            episodes.append(episodes_data_dict)

        return cls.transformer_schema(source_url=extraction_object.url, data=json.loads(data), episodes=episodes)

    @staticmethod
    @app.task
    def task(extraction_id):
        GDACSTransformHandler().handle_transformation(extraction_id)
