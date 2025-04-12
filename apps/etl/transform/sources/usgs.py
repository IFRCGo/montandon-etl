import json

from pystac_monty.sources.usgs import USGSDataSource, USGSTransformer

from apps.etl.models import ExtractionData
from apps.etl.transform.sources.handler import BaseTransformerHandler
from main.celery import CeleryQueue, app


class USGSTransformHandler(BaseTransformerHandler[USGSTransformer, USGSDataSource]):
    transformer_class = USGSTransformer
    transformer_schema = USGSDataSource

    @classmethod
    def get_schema_data(cls, extraction_obj):
        all_children = ExtractionData.objects.filter(parent=extraction_obj)

        losses_data = []
        for child_item in all_children:
            obj = ExtractionData.objects.filter(id=child_item.id).first()
            if obj and obj.resp_data:
                with obj.resp_data.open() as file_data:
                    data = json.loads(file_data.read())
                losses_data.append(data)

        with extraction_obj.resp_data.open() as file_data:
            data = file_data.read()

        losses_data = json.dumps(losses_data)
        # FIXME: Why are we setting lossed_data to None?
        if not losses_data:
            losses_data = None

        return cls.transformer_schema(source_url=extraction_obj.url, data=data, losses_data=losses_data)

    @staticmethod
    @app.task(queue=CeleryQueue.TRANSFORM)
    def task(extraction_id):
        USGSTransformHandler().handle_transformation(extraction_id)
