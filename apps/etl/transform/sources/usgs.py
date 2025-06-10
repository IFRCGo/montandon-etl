import json

from pystac_monty.sources.common import DataType, File
from pystac_monty.sources.usgs import USGSDataSource, USGSDataSourceType, USGSTransformer

from apps.etl.models import ExtractionData
from apps.etl.transform.sources.handler import BaseTransformerHandler
from apps.etl.utils import write_into_temp_file
from main.celery import CeleryQueue, app


class USGSTransformHandler(BaseTransformerHandler[USGSTransformer, USGSDataSource]):
    transformer_class = USGSTransformer
    transformer_schema = USGSDataSource

    @classmethod
    def get_schema_data(cls, extraction_obj):
        losses_data_qs = ExtractionData.objects.filter(parent=extraction_obj)

        losses_data = []
        for losses_data_obj in losses_data_qs.all():
            if losses_data_obj.resp_data is None:
                continue
            with losses_data_obj.resp_data.open() as file_data:
                data = json.loads(file_data.read())
            losses_data.append(data)

        # Write losses_data (which is JSON) to a temp file in text mode
        losses_data_path = write_into_temp_file(json.dumps(losses_data).encode("utf-8")).name

        # Read the main extraction object data (as bytes)
        with extraction_obj.resp_data.open() as file_data:
            data = file_data.read()

        # Write raw bytes to a temp file
        data_path = write_into_temp_file(data).name

        return cls.transformer_schema(
            USGSDataSourceType(
                source_url=extraction_obj.url,
                event_data=File(path=data_path, data_type=DataType.FILE),
                loss_data=File(path=losses_data_path, data_type=DataType.FILE),
            )
        )

    @staticmethod
    @app.task(queue=CeleryQueue.TRANSFORM)
    def task(extraction_id):
        USGSTransformHandler().handle_transformation(extraction_id)
