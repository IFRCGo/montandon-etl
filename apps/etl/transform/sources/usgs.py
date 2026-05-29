import json
import os
from pathlib import Path

from django.conf import settings
from pystac_monty.sources.common import DataType, File
from pystac_monty.sources.usgs import USGSDataSource, USGSDataSourceType, USGSTransformer

from apps.etl.models import ExtractionData
from apps.etl.transform.sources.handler import BaseTransformerHandler
from apps.etl.utils import write_into_temp_file
from main.celery import CeleryQueue, app
from main.configs import etl_config


class USGSTransformHandler(BaseTransformerHandler[USGSTransformer, USGSDataSource]):
    transformer_class = USGSTransformer
    transformer_schema = USGSDataSource

    @classmethod
    def get_schema_data(cls, extraction_obj, dir_uuid: str):
        from apps.etl.extraction.sources.usgs.extract import USGSExtractionMetadataType

        tmp_dir_path = Path("/tmp") / extraction_obj.get_source_display() / dir_uuid
        if not os.path.isdir(tmp_dir_path):
            os.makedirs(tmp_dir_path, exist_ok=True)

        losses_data_qs = ExtractionData.objects.filter(parent=extraction_obj, status=ExtractionData.Status.SUCCESS)

        losses_data = []
        alerts_data = []
        for losses_data_obj in losses_data_qs.all():
            if losses_data_obj.resp_data is None:
                continue
            if losses_data_obj.metadata["type"] == USGSExtractionMetadataType.LOSSE:
                with losses_data_obj.resp_data.open() as file_data:
                    data = json.loads(file_data.read())
                    losses_data.append(data)
            elif losses_data_obj.metadata["type"] == USGSExtractionMetadataType.ALERTS:
                with losses_data_obj.resp_data.open() as file_data:
                    data = json.loads(file_data.read())
                    alerts_data.append(data)

        # Write losses_data (which is JSON) to a temp file in text mode
        losses_data_path = write_into_temp_file(json.dumps(losses_data).encode("utf-8"), tmp_dir_path)

        # Write alerts data to a temp file
        alerts_data_path = write_into_temp_file(json.dumps(alerts_data).encode("utf-8"), tmp_dir_path)

        # Read the main extraction object data (as bytes)
        with extraction_obj.resp_data.open() as file_data:
            data = file_data.read()

        # Write raw bytes to a temp file
        data_path = write_into_temp_file(data, tmp_dir_path)

        result = cls.transformer_schema(
            data=USGSDataSourceType(
                source_url=extraction_obj.url,
                event_data=File(path=data_path.name, data_type=DataType.FILE),
                loss_data=File(path=losses_data_path.name, data_type=DataType.FILE),
                alerts_data=File(path=alerts_data_path.name, data_type=DataType.FILE),
            ),
            eoapi_url=etl_config.EOAPI_STAC_API_PUBLIC,
        )

        return result

    @staticmethod
    @app.task(queue=CeleryQueue.TRANSFORM)
    def task(extraction_id):
        USGSTransformHandler().handle_transformation(extraction_id, settings.USGS_TRANSFORMER_VERSION)
