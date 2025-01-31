import logging
import uuid
from abc import ABC, abstractmethod
from typing import List, Union

from pystac_monty.sources.gdacs import GDACSDataSource, GDACSTransformer
from pystac_monty.sources.glide import GlideDataSource, GlideTransformer
from pystac_monty.sources.idu import IDUDataSource, IDUTransformer

from apps.etl.models import ExtractionData, PyStacLoadData, Transform
from main.managers import BulkCreateManager

logger = logging.getLogger(__name__)

ITEM_TYPE_COLLECTION_ID_MAP = {
    "idu-events": PyStacLoadData.ItemType.EVENT,
    "idu-impacts": PyStacLoadData.ItemType.IMPACT,
}


class BaseTransformerHandler(ABC):

    def __init__(
        self,
        extraction_id: int,
        transformer: Union[
            GDACSTransformer,
            GlideTransformer,
            IDUTransformer,
        ],
        transformer_schema: Union[
            List[GDACSDataSource],
            GlideDataSource,
            IDUDataSource,
        ],
    ):
        self.extraction_id = extraction_id
        self.transformer = transformer
        self.transformer_schema = transformer_schema

    @abstractmethod
    def get_schema_data(self, extraction_id):
        pass

    def handle_transformation(self):
        logger.info("Transformation started")
        extraction_instance = ExtractionData.objects.filter(id=self.extraction_id).first()

        transform_obj = Transform.objects.create(
            extraction=extraction_instance,
            status=Transform.Status.PENDING,
        )

        try:
            schema = self.get_schema_data()
            transformer = self.transformer(schema)
            transformed_items = transformer.make_items()

            transform_obj.status = Transform.Status.SUCCESS
            transform_obj.save(update_fields=["status"])

            self.load_stac_item_to_queue(transformed_items, transform_obj.id)

            logger.info("Transformation ended")

        except Exception as e:
            logger.error("Transformation failed", exc_info=True, extra={"extraction_id": extraction_instance.id})
            transform_obj.status = Transform.Status.FAILED
            transform_obj.save(update_fields=["status"])
            # FIXME: Check if this creates duplicate entry in Sentry. if yes, remove this.
            raise e

    def load_stac_item_to_queue(self, transform_items, transform_obj_id):
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
