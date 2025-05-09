import logging

from pystac_monty.sources.gdacs import (
    GDACSDataSource,
    GDACSDataSourceType,
    GDACSTransformer,
)

from apps.etl.transform.sources.handler import BaseTransformerHandler
from apps.etl.utils import write_into_temp_file
from main.celery import app

logger = logging.getLogger(__name__)

# FIXME: start_end_handler base zzz


class GDACSTransformHandler(BaseTransformerHandler[GDACSTransformer, GDACSDataSource]):
    transformer_class = GDACSTransformer
    transformer_schema = GDACSDataSource

    @classmethod
    def get_schema_data(cls, extraction_object):
        with extraction_object.resp_data.open("rb") as f:
            file_content = f.read()
        data_file = write_into_temp_file(file_content)

        episodes = []
        event_objects = extraction_object.child_extractions.all()
        for episode_obj in event_objects:
            episodes_data_dict = {}

            with episode_obj.resp_data.open("rb") as f:
                file_content = f.read()
            episode_data_temp_file = write_into_temp_file(file_content)

            episodes_data_dict[GDACSDataSourceType.EVENT] = (episode_obj.url, episode_data_temp_file.name)
            geometry_objects = episode_obj.child_extractions.all()

            for geometry_detail in geometry_objects:
                with geometry_detail.resp_data.open("rb") as f:
                    file_content = f.read()
                geometry_detail_temp_file = write_into_temp_file(file_content)

                episodes_data_dict[GDACSDataSourceType.GEOMETRY] = (geometry_detail.url, geometry_detail_temp_file.name)

            episodes.append(episodes_data_dict)

        return cls.transformer_schema(source_url=extraction_object.url, data=data_file.name, episodes=episodes)

    @staticmethod
    @app.task(rate_limit="50/m")
    def task(extraction_id):
        GDACSTransformHandler().handle_transformation(extraction_id)
