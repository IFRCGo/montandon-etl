import logging
import uuid
from celery import shared_task
from pystac_monty.sources.noaa import NoaaIbtracsSource, NoaaIbtracsTransformer

from apps.etl.models import ExtractionData, Transform, PyStacLoadData
from apps.etl.utils import read_file_data
from main.managers import BulkCreateManager

logger = logging.getLogger(__name__)

noaa_item_type_map = {
    "ibtracs-events": PyStacLoadData.ItemType.EVENT,
    "ibtracs-hazards": PyStacLoadData.ItemType.HAZARD,
}


@shared_task
def transform_event_data(event_extraction_id):
    logger.debug("Transform event data for noaa")
    logger.info("Transform started for event data for noaa")
    noaa_instance = ExtractionData.objects.get(id=event_extraction_id)
    # data = read_file_data(noaa_instance.resp_data)
    transform_obj = Transform.objects.create(
        extraction=noaa_instance,
        status=Transform.Status.PENDING,
    )

    bulk_mgr = BulkCreateManager(chunk_size=1000)
    try:
        transformer = NoaaIbtracsTransformer(NoaaIbtracsSource(source_url=noaa_instance.url, data=noaa_instance.resp_data))
        transformed_event_items = transformer.make_items()

        transform_obj.status = Transform.Status.SUCCESS
        transform_obj.save(update_fields=["status"])
    except Exception as e:
        logger.error("Noaa  transformation failed", exc_info=True, extra={"extraction_id": noaa_instance.id})
        transform_obj.status = Transform.Status.FAILED
        transform_obj.save(update_fields=["status"])
        raise e
    for item in transformed_event_items:
        item_type = noaa_item_type_map[item.collection_id]
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

    logger.info("Transformation ended for noaa  data")
