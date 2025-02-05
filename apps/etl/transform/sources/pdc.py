from .handler import BaseTransformerHandler


class PDCTransformHandler(BaseTransformerHandler):
    transformer = PDCTransformer
    transformer_schema = PDCDataSource

    @classmethod
    def get_schema_data(cls, extraction_obj: ExtractionData):
        with extraction_obj.resp_data.open() as file_data:
            data = file_data.read()

        return cls.transformer_schema(source_url=extraction_obj.url, data=data)

    @staticmethod
    @app.task
    def task(extraction_id):
        return PDCTransformHandler().handle_transformation(extraction_id)
