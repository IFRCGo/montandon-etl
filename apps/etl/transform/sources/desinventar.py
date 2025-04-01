import logging
import tempfile

from pystac_monty.sources.desinventar import (
    DesinventarDataSource,
    DesinventarTransformer,
)

from apps.etl.models import ExtractionData
from apps.etl.transform.sources.handler import BaseTransformerHandler
from main.celery import app

logger = logging.getLogger(__name__)


class DesinventarTransformHandler(BaseTransformerHandler[DesinventarTransformer, DesinventarDataSource]):
    transformer_class = DesinventarTransformer
    transformer_schema = DesinventarDataSource

    @classmethod
    def get_schema_data(cls, extraction_obj: ExtractionData):
        from apps.etl.extraction.sources.desinventar.extract import DesInventarExtractionInputMetadata

        metadata: dict | None = extraction_obj.metadata
        if not metadata:
            raise Exception("Metadata is not defined")
        input_metadata = metadata.get("input", {})
        input_metadata = DesInventarExtractionInputMetadata(
            country_code=input_metadata.get("country_code"),
            iso3=input_metadata.get("iso3"),
        )

        with extraction_obj.resp_data.open("rb") as f:
            file_content = f.read()
        # FIXME: Why do we have delete=False? We need to delete this in post action
        tmp_zip_file = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
        tmp_zip_file.write(file_content)

        return cls.transformer_schema(
            tmp_zip_file=tmp_zip_file,
            source_url=extraction_obj.url,
            country_code=input_metadata.country_code,
            iso3=input_metadata.iso3,
        )

    @staticmethod
    @app.task
    def task(extraction_id):
        DesinventarTransformHandler().handle_transformation(extraction_id)
