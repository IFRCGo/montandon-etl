import json
import tempfile

from pystac_monty.sources.usgs import USGSDataSource, USGSTransformer

from apps.etl.models import ExtractionData
from apps.etl.transform.sources.handler import BaseTransformerHandler
from main.celery import CeleryQueue, app


class USGSTransformHandler(BaseTransformerHandler[USGSTransformer, USGSDataSource]):
    transformer_class = USGSTransformer
    transformer_schema = USGSDataSource

    @classmethod
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
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w", encoding="utf-8") as tmp_file:
            json.dump(losses_data, tmp_file)
            losses_data_path = tmp_file.name

        # Read the main extraction object data (as bytes)
        with extraction_obj.resp_data.open() as file_data:
            data = file_data.read()

        # Write raw bytes to a temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp_data_file:
            tmp_data_file.write(data)
            data_path = tmp_data_file.name

        return cls.transformer_schema(source_url=extraction_obj.url, data=data_path, losses_data=losses_data_path)

    @staticmethod
    @app.task(queue=CeleryQueue.TRANSFORM)
    def task(extraction_id):
        USGSTransformHandler().handle_transformation(extraction_id)
