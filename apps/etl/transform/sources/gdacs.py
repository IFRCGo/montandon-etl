import logging
from tempfile import _TemporaryFileWrapper

from pystac_monty.sources.common import DataType, File, GdacsDataSourceType, GdacsEpisodes, GenericDataSource
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
    def get_schema_data(cls, extraction_object) -> tuple[GDACSDataSource, list[_TemporaryFileWrapper[bytes]]]:
        with extraction_object.resp_data.open("rb") as f:
            file_content = f.read()
        data_file = write_into_temp_file(file_content)

        episodes = []
        event_objects = extraction_object.child_extractions.all()
        for episode_obj in event_objects:
            with episode_obj.resp_data.open("rb") as f:
                file_content = f.read()
            episode_data_temp_file = write_into_temp_file(file_content)

            event_episode_data = GdacsEpisodes(
                type=GDACSDataSourceType.EVENT,
                data=GenericDataSource(
                    source_url=episode_obj.url, input_data=File(path=episode_data_temp_file.name, data_type=DataType.FILE)
                ),
            )
            geometry_object = episode_obj.child_extractions.all().first()

            with geometry_object.resp_data.open("rb") as f:
                file_content = f.read()
            geometry_detail_temp_file = write_into_temp_file(file_content)
            geometry_episode_data = GdacsEpisodes(
                type=GDACSDataSourceType.GEOMETRY,
                data=GenericDataSource(
                    source_url=geometry_object.url,
                    input_data=File(path=geometry_detail_temp_file.name, data_type=DataType.FILE),
                ),
            )

            episode_data_tuple = (event_episode_data, geometry_episode_data)
            episodes.append(episode_data_tuple)

        result = cls.transformer_schema(
            data=GdacsDataSourceType(
                source_url=extraction_object.url,
                event_data=File(path=data_file.name, data_type=DataType.FILE),
                episodes=episodes,
            )
        )

        tmp_files = [data_file, episode_data_temp_file, geometry_detail_temp_file]
        return result, tmp_files

    @staticmethod
    @app.task(rate_limit="50/m")
    def task(extraction_id):
        GDACSTransformHandler().handle_transformation(extraction_id)
