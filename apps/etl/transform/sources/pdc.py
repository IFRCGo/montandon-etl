import json
import logging
import tempfile

from pystac_monty.sources.pdc import PDCDataSource, PDCTransformer

from apps.etl.models import ExtractionData
from main.celery import app

from .handler import BaseTransformerHandler

logger = logging.getLogger(__name__)


class PDCTransformHandler(BaseTransformerHandler[PDCTransformer, PDCDataSource]):
    transformer_class = PDCTransformer
    transformer_schema = PDCDataSource

    @classmethod
    def get_schema_data(cls, extraction_obj: ExtractionData):
        metadata: dict | None = extraction_obj.metadata
        if not metadata:
            raise Exception("Metadata is not defined")
        input_metadata = metadata.get("input", {})

        from apps.etl.extraction.sources.pdc.extract import PdcExposureInputMetadata

        input_metadata = PdcExposureInputMetadata(**input_metadata)

        geo_json_obj = ExtractionData.objects.get(id=input_metadata.geojson_id)

        with geo_json_obj.resp_data.open("rb") as f:
            file_content = f.read()
        # FIXME: Why do we have delete=False? We need to delete this in post action
        tmp_geojson_file = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        tmp_geojson_file.write(file_content)

        with extraction_obj.parent.resp_data.open("rb") as f:
            file_content = f.read()
        # FIXME: Why do we have delete=False? We need to delete this in post action
        tmp_hazard_file = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        tmp_hazard_file.write(file_content)

        with extraction_obj.resp_data.open("rb") as f:
            file_content = f.read()
        # FIXME: Why do we have delete=False? We need to delete this in post action
        tmp_exposure_detail_file = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        tmp_exposure_detail_file.write(file_content)

        data = {
            "hazards_file_path": tmp_hazard_file.name,
            "exposure_timestamp": input_metadata.exposure_id,
            "uuid": input_metadata.hazard_uuid,
            "exposure_detail_file_path": tmp_exposure_detail_file.name,
            "geojson_file_path": tmp_geojson_file.name,
        }

        return cls.transformer_schema(source_url=extraction_obj.url, data=json.dumps(data))

    @staticmethod
    @app.task
    def task(extraction_id):
        return PDCTransformHandler().handle_transformation(extraction_id)
