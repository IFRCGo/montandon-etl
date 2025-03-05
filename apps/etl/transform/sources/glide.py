import logging
import uuid

from celery import shared_task
from pystac_monty.sources.glide import GlideDataSource, GlideTransformer

from apps.etl.models import ExtractionData, PyStacLoadData, Transform
from apps.etl.utils import read_file_data
from main.managers import BulkCreateManager

logger = logging.getLogger(__name__)

glide_item_type_map = {
    "glide-events": PyStacLoadData.ItemType.EVENT,
    "glide-hazards": PyStacLoadData.ItemType.HAZARD,
}


@shared_task
def transform_glide_event_data(extraction_id):
    logger.info("Transformation started for glide data")
    glide_instance = ExtractionData.objects.get(id=extraction_id)

    if not glide_instance.resp_data:
        logger.info("Transformation ended due to no data")
        return

    data = read_file_data(glide_instance.resp_data)

    transform_obj = Transform.objects.create(
        extraction=glide_instance,
        status=Transform.Status.PENDING,
    )

    bulk_mgr = BulkCreateManager(chunk_size=1000)
    try:
        transformer = GlideTransformer(GlideDataSource(source_url=glide_instance.url, data=data))
        transformed_event_items = transformer.make_items()

        transform_obj.status = Transform.Status.SUCCESS
        transform_obj.save(update_fields=["status"])
    except Exception as e:
        logger.error("Glide transformation failed", exc_info=True, extra={"extraction_id": glide_instance.id})
        transform_obj.status = Transform.Status.FAILED
        transform_obj.save(update_fields=["status"])
        # FIXME: Check if this creates duplicate entry in Sentry. if yes, remove this.
        raise e

    for item in transformed_event_items:
        item_type = glide_item_type_map[item.collection_id]
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

    logger.info("Transformation ended for glide data")
