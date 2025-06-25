import logging
import os

from pystac_monty.sources.common import DataType, File
from pystac_monty.sources.pdc import PDCDataSource, PDCDataSourceType, PDCTransformer

from apps.etl.models import ExtractionData
from apps.etl.utils import write_into_temp_file
from main.celery import CeleryQueue, app

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
        from apps.etl.extraction.sources.pdc.extract import PDCExtractionMetadata

        input_metadata = PDCExtractionMetadata(**metadata)

        geo_json_obj = ExtractionData.objects.get(id=input_metadata.exposure_detail.geojson_id)

        with extraction_obj.parent.resp_data.open("rb") as f:
            file_content = f.read()
        # FIXME: Why do we have delete=False? We need to delete this in post action
        tmp_hazard_file = write_into_temp_file(file_content)

        with extraction_obj.resp_data.open("rb") as f:
            file_content = f.read()
        # FIXME: Why do we have delete=False? We need to delete this in post action
        tmp_exposure_detail_file = write_into_temp_file(file_content)

        result = cls.transformer_schema(
            data=PDCDataSourceType(
                source_url=extraction_obj.parent.url,
                uuid=input_metadata.exposure_detail.hazard_uuid,
                hazard_data=File(path=tmp_hazard_file.name, data_type=DataType.FILE),
                exposure_detail_data=File(path=tmp_exposure_detail_file.name, data_type=DataType.FILE),
                geojson_path=geo_json_obj.resp_data.path,
            )
        )

        for tmp_file in [tmp_hazard_file, tmp_exposure_detail_file]:
            if os.path.exists(tmp_file.name):
                os.remove(tmp_file.name)
        return result

    @staticmethod
    @app.task(queue=CeleryQueue.TRANSFORM)
    def task(extraction_id):
        return PDCTransformHandler().handle_transformation(extraction_id)
