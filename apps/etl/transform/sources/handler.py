import logging
import uuid
from abc import ABC

from apps.etl.models import ExtractionData, PyStacLoadData, Transform
from main.celery import app
from main.managers import BulkCreateManager

logger = logging.getLogger(__name__)

ITEM_TYPE_COLLECTION_ID_MAP = {
    "idmc-idu-events": PyStacLoadData.ItemType.EVENT,
    "idmc-idu-impacts": PyStacLoadData.ItemType.IMPACT,
    "idmc-gidd-events": PyStacLoadData.ItemType.EVENT,
    "idmc-gidd-impacts": PyStacLoadData.ItemType.IMPACT,
    "gfd-events": PyStacLoadData.ItemType.EVENT,
    "gfd-impacts": PyStacLoadData.ItemType.IMPACT,
    "gfd-hazards": PyStacLoadData.ItemType.HAZARD,
    "ifrcevent-events": PyStacLoadData.ItemType.EVENT,
    "ifrcevent-impacts": PyStacLoadData.ItemType.IMPACT,
    "desinventar-events": PyStacLoadData.ItemType.EVENT,
    "desinventar-impacts": PyStacLoadData.ItemType.IMPACT,
    "desinventar-hazards": PyStacLoadData.ItemType.HAZARD,
    "pdc-events": PyStacLoadData.ItemType.EVENT,
    "pdc-hazards": PyStacLoadData.ItemType.HAZARD,
    "pdc-impacts": PyStacLoadData.ItemType.IMPACT,
}


class BaseTransformerHandler(ABC):
    @classmethod
    def get_schema_data(cls, extraction_obj: ExtractionData):
        raise NotImplementedError()

    @classmethod
    def handle_transformation(cls, extraction_id):
        logger.info("Transformation started")
        extraction_obj = ExtractionData.objects.filter(id=extraction_id).first()
        if not extraction_obj.resp_data:
            logger.info("Transformation ended due to no data")
            return

        transform_obj = Transform.objects.create(
            extraction=extraction_obj,
            status=Transform.Status.PENDING,
        )

        try:
            schema = cls.get_schema_data(extraction_obj)
            transformer = cls.transformer(schema)
            transformed_items = transformer.make_items()

            transform_obj.status = Transform.Status.SUCCESS
            transform_obj.save(update_fields=["status"])

            cls.load_stac_item_to_queue(transformed_items, transform_obj.id)

            logger.info("Transformation ended")

        except Exception as e:
            logger.error("Transformation failed", exc_info=True, extra={"extraction_id": extraction_obj.id})
            transform_obj.status = Transform.Status.FAILED
            transform_obj.save(update_fields=["status"])
            # FIXME: Check if this creates duplicate entry in Sentry. if yes, remove this.
            raise e

    @classmethod
    def load_stac_item_to_queue(cls, transform_items, transform_obj_id):
        logger.info("Loading data into queue")

        transform_obj = Transform.objects.filter(id=transform_obj_id).first()
        bulk_mgr = BulkCreateManager(chunk_size=1000)
        for item in transform_items:
            item_type = ITEM_TYPE_COLLECTION_ID_MAP[item.collection_id]
            transformed_item_dict = item.to_dict()
            transformed_item_dict["properties"]["monty:etl_id"] = str(uuid.uuid4())
            bulk_mgr.add(
                PyStacLoadData(
                    transform_id=transform_obj,
                    item=transformed_item_dict,
                    collection_id=item.collection_id,
                    item_type=item_type,
                    load_status=PyStacLoadData.LoadStatus.PENDING,
                )
            )

        bulk_mgr.done()

        transform_obj.is_loaded = True
        transform_obj.save(update_fields=["is_loaded"])

        logger.info("Loading data into queue successfull")

    @staticmethod
    @app.task
    def task(extraction_id):
        """
        Not NotImplemented due to celery limitation with classmethod
        Eg: return XYZTransformHandler.handle_transformation(extraction_id)
        """
        raise NotImplementedError()
