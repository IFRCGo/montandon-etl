from pystac_monty.sources.idu import IDUDataSource, IDUTransformer

from apps.etl.models import ExtractionData
from apps.etl.transform.sources.handler import BaseTransformerHandler


class IDUTransformHandler(BaseTransformerHandler):
    def __init__(self, extraction_id: str, transformer=IDUTransformer, transformer_schema=IDUDataSource):
        super().__init__(extraction_id, transformer, transformer_schema)

    def get_schema_data(self):
        extraction_obj = ExtractionData.objects.filter(id=self.extraction_id).first()
        with extraction_obj.resp_data.open() as file_data:
            data = file_data.read()

        return self.transformer_schema(source_url=extraction_obj.url, data=data)
