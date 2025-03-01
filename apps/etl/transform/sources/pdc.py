import json

from pystac_monty.sources.pdc import PDCDataSource, PDCTransformer

from apps.etl.models import ExtractionData
from main.celery import app

from .handler import BaseTransformerHandler


class PDCTransformHandler(BaseTransformerHandler):
    transformer = PDCTransformer
    transformer_schema = PDCDataSource

    @classmethod
    def get_schema_data(cls, extraction_obj: ExtractionData):
        source_url = extraction_obj.url
        data = {
            "hazards_file_path": extraction_obj.parent.resp_data.path,
            "exposure_timestamp": extraction_obj.metadata["exposure_id"],
            "uuid": extraction_obj.metadata["uuid"],
            "exposure_detail_file_path": extraction_obj.resp_data.path,
            "geojson_file_path": extraction_obj.parent.metadata["geojson_file_path"] or None,
        }
        return cls.transformer_schema(source_url=source_url, data=json.dumps(data))

    @staticmethod
    @app.task
    def task(extraction_id):
        return PDCTransformHandler().handle_transformation(extraction_id)
