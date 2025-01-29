import logging
import uuid

from apps.etl.models import ExtractionData, PyStacLoadData, Transform
from main.managers import BulkCreateManager

logger = logging.getLogger(__name__)

ITEM_TYPE_COLLECTION_ID_MAP = {
    "idu-events": PyStacLoadData.ItemType.EVENT,
    "idu-hazards": PyStacLoadData.ItemType.HAZARD,
}


class BaseTransformer:
    def __init__(self, extraction_id, transformer, transformer_schema):
        self.extraction_id = extraction_id
        self.transformer = transformer
        self.transformer_schema = transformer_schema

    def transform_data(self):
        logger.info("Transformation started for glide data")
        extraction_instance = ExtractionData.objects.get(id=self.extraction_id)

        transform_obj = Transform.objects.create(
            extraction=extraction_instance,
            status=Transform.Status.PENDING,
        )

        try:
            transformer = self.transformer(self.transformer_schema)
            transformed_items = transformer.make_items()

            transform_obj.status = Transform.Status.SUCCESS
            transform_obj.save(update_fields=["status"])

            logger.info("Transformation ended for glide data")

            return {"items": transformed_items, "id": transform_obj.id}
        except Exception as e:
            logger.error("Glide transformation failed", exc_info=True, extra={"extraction_id": extraction_instance.id})
            transform_obj.status = Transform.Status.FAILED
            transform_obj.save(update_fields=["status"])
            # FIXME: Check if this creates duplicate entry in Sentry. if yes, remove this.
            raise e

    def load_stac_item_to_queue(self, transform_data):
        logger.info("Loading data into queue")

        transform_obj = Transform.objects.filter(id=transform_data["id"]).first()
        bulk_mgr = BulkCreateManager(chunk_size=1000)
        for item in transform_data["items"]:
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
