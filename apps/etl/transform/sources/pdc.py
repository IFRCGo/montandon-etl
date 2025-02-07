from main.celery import app

from .handler import BaseTransformerHandler


class PDCTransformHandler(BaseTransformerHandler):
    transformer = PDCTransformer
    transformer_schema = PDCDataSource

    @classmethod
    def get_schema_data(cls, extraction_obj: ExtractionData):
        data = extraction_obj.resp_data.file.url

        return cls.transformer_schema(source_url=extraction_obj.url, data=data)

    @staticmethod
    @app.task
    def task(extraction_id):
        return PDCTransformHandler().handle_transformation(extraction_id)
