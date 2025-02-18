import logging
import uuid

from celery import shared_task
from pystac_monty.geocoding import GAULGeocoder

from apps.etl.models import ExtractionData, PyStacLoadData, Transform
from main.managers import BulkCreateManager

logger = logging.getLogger(__name__)

collection_and_item_type_map = {
    "emdat-events": PyStacLoadData.ItemType.EVENT,
    "emdat-hazards": PyStacLoadData.ItemType.HAZARD,
    "emdat-impacts": PyStacLoadData.ItemType.IMPACT,
}

# XXX: Local file is used
GEOCODER = GAULGeocoder(gpkg_path="/code/gaul2014_2015.gpkg")


@shared_task
def transform_data(source, transformer, data_source, extraction_id, data):
    logger.info(f"Transformation started for {source} data")
    ext_instance = ExtractionData.objects.get(id=extraction_id)

    # create transform object
    transform_obj = Transform.objects.create(
        extraction=ext_instance,
        status=Transform.Status.PENDING,
    )

    # initialize bulk manager to create the PyStacLoadData in bulk.
    bulk_mgr = BulkCreateManager(chunk_size=1000)

    try:
        # Get transformer for each source and transform it to stac item..
        transformer = transformer(data=data_source(source_url=ext_instance.url, data=data), geocoder=GEOCODER)
        transformed_items = transformer.make_items()

        # update transformation status to success
        transform_obj.status = Transform.Status.SUCCESS
        transform_obj.save(update_fields=["status"])
    except Exception as e:
        logger.error("Transformation failed", exc_info=True, extra={"extraction_id": ext_instance.id, "source": source})
        # update transformation status to success
        transform_obj.status = Transform.Status.FAILED
        transform_obj.save(update_fields=["status"])
        # FIXME: Check if this creates duplicate entry in Sentry. if yes, remove this.
        raise e

    # create objects into PyStacLoadData table
    for item in transformed_items:
        item_type = collection_and_item_type_map[item.collection_id]
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

    logger.info("Transformation ended for emdat data")
