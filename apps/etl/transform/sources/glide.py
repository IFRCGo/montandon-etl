from pystac_monty.sources.glide import GlideDataSource, GlideTransformer

from apps.etl.transform.sources.handler import BaseTransformerHandler
from main.celery import app
from main.configs import etl_config


class GlideTransformHandler(BaseTransformerHandler[GlideTransformer, GlideDataSource]):
    transformer_class = GlideTransformer
    transformer_schema = GlideDataSource

    @classmethod
    def get_schema_data(cls, extraction_obj):
        with extraction_obj.resp_data.open() as file_data:
            data = file_data.read()

        return cls.transformer_schema(source_url=f"{etl_config.GLIDE_URL}/glide/jsonglideset.jsp", data=data)

    @staticmethod
    @app.task
    def task(extraction_id):
        GlideTransformHandler().handle_transformation(extraction_id)
