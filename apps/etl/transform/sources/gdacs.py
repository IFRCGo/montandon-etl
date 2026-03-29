import logging
import os
from pathlib import Path

from django.conf import settings
from pystac_monty.sources.common import DataType, File, GdacsDataSourceType, GdacsEpisodes, GenericDataSource
from pystac_monty.sources.gdacs import (
    GDACSDataSource,
    GDACSDataSourceType,
    GDACSTransformer,
)

from apps.etl.models import ExtractionData
from apps.etl.transform.sources.handler import BaseTransformerHandler
from apps.etl.utils import write_into_temp_file
from main.celery import CeleryQueue, app
from main.configs import etl_config

logger = logging.getLogger(__name__)

# FIXME: start_end_handler base zzz


class GDACSTransformHandler(BaseTransformerHandler[GDACSTransformer, GDACSDataSource]):
    transformer_class = GDACSTransformer
    transformer_schema = GDACSDataSource

    @classmethod
    def get_schema_data(cls, extraction_object, dir_uuid: str):
        from apps.etl.extraction.sources.gdacs.extract import GdacsExtractionMetadataType

        tmp_dir_path = Path("/tmp") / extraction_object.get_source_display() / dir_uuid
        if not os.path.isdir(tmp_dir_path):
            os.makedirs(tmp_dir_path, exist_ok=True)

        with extraction_object.resp_data.open("rb") as f:
            file_content = f.read()
        data_file = write_into_temp_file(file_content, tmp_dir_path)

        episodes = []
        event_objects = extraction_object.child_extractions.filter(status=ExtractionData.Status.SUCCESS)
        for episode_obj in event_objects:
            event_episode_data = geometry_episode_data = impact_episode_data = None
            if episode_obj and episode_obj.resp_data:
                with episode_obj.resp_data.open("rb") as f:
                    file_content = f.read()
                episode_data_temp_file = write_into_temp_file(file_content, tmp_dir_path)

                event_episode_data = GdacsEpisodes(
                    type=GDACSDataSourceType.EVENT,
                    data=GenericDataSource(
                        source_url=episode_obj.url,
                        input_data=File(path=episode_data_temp_file.name, data_type=DataType.FILE),
                    ),
                    hazard_type=episode_obj.metadata["event_params"]["eventtype"],
                )
                geometry_object = episode_obj.child_extractions.filter(
                    status=ExtractionData.Status.SUCCESS, metadata__type=GdacsExtractionMetadataType.GEOMETRY
                ).first()

                if geometry_object and geometry_object.resp_data:
                    with geometry_object.resp_data.open("rb") as f:
                        file_content = f.read()
                    geometry_detail_temp_file = write_into_temp_file(file_content, tmp_dir_path)
                    geometry_episode_data = GdacsEpisodes(
                        type=GDACSDataSourceType.GEOMETRY,
                        data=GenericDataSource(
                            source_url=geometry_object.url,
                            input_data=File(path=geometry_detail_temp_file.name, data_type=DataType.FILE),
                        ),
                        hazard_type=geometry_object.metadata["event_params"]["eventtype"],
                    )

                impact_object = episode_obj.child_extractions.filter(
                    status=ExtractionData.Status.SUCCESS, metadata__type=GdacsExtractionMetadataType.IMPACT
                ).first()
                if impact_object and impact_object.resp_data:
                    with impact_object.resp_data.open("rb") as f:
                        file_content = f.read()
                        impact_detail_temp_file = write_into_temp_file(file_content, tmp_dir_path)
                        impact_episode_data = GdacsEpisodes(
                            type=GDACSDataSourceType.IMPACT,
                            data=GenericDataSource(
                                source_url=impact_object.url,
                                input_data=File(path=impact_detail_temp_file.name, data_type=DataType.FILE),
                            ),
                            hazard_type=impact_object.metadata["event_params"]["eventtype"],
                        )
            if event_episode_data and geometry_episode_data:
                # Each item is a tuple of event, geometry and impact objects
                episodes.append((event_episode_data, geometry_episode_data, impact_episode_data))

        result = cls.transformer_schema(
            data=GdacsDataSourceType(
                source_url=extraction_object.url,
                event_data=File(path=data_file.name, data_type=DataType.FILE),
                episodes=episodes,
            ),
            eoapi_url=etl_config.EOAPI_STAC_API,
        )

        return result

    @staticmethod
    @app.task(rate_limit="50/m", queue=CeleryQueue.TRANSFORM)
    def task(extraction_id):
        GDACSTransformHandler().handle_transformation(extraction_id, settings.GDACS_TRANSFORMER_VERSION)
