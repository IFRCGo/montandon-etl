import logging
import uuid

from celery import shared_task
from django.conf import settings
from pystac_monty.geocoding import GAULGeocoder
from pystac_monty.sources.usgs import USGSDataSource, USGSTransformer

from apps.etl.models import ExtractionData, PyStacLoadData, Transform
from apps.etl.utils import read_file_data
from main.logging import log_extra
from main.managers import BulkCreateManager

logger = logging.getLogger(__name__)

usgs_item_type_map = {
    "usgs-events": PyStacLoadData.ItemType.EVENT,
    "usgs-hazards": PyStacLoadData.ItemType.HAZARD,
    "usgs-impacts": PyStacLoadData.ItemType.IMPACT,
}


@shared_task
def transform_usgs_event_data(extraction_id):
    logger.info("Transformation started for usgs data")
    usgs_instance = ExtractionData.objects.get(id=extraction_id)

    if not usgs_instance.resp_data:
        logger.info("Transformation ended due to no data")
        return

    data = read_file_data(usgs_instance.resp_data)

    transform_obj = Transform.objects.create(
        extraction=usgs_instance,
        status=Transform.Status.PENDING,
        trace_id=usgs_instance.trace_id,
    )

    bulk_mgr = BulkCreateManager(chunk_size=1000)
    geocoder = GAULGeocoder(gpkg_path=None, service_base_url=settings.GEOCODER_URL)
    try:
        transformer = USGSTransformer(USGSDataSource(source_url=usgs_instance.url, data=data), geocoder=geocoder)
        transformed_event_items = transformer.make_items()

        transform_obj.status = Transform.Status.SUCCESS
        transform_obj.save(update_fields=["status"])
    except Exception as e:
        logger.error("usgs transformation failed", exc_info=True, extra=log_extra({"extraction_id": usgs_instance.id}))
        transform_obj.status = Transform.Status.FAILED
        transform_obj.save(update_fields=["status"])
        raise e

    for item in transformed_event_items:
        item_type = usgs_item_type_map[item.collection_id]
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

    logger.info("Transformation ended for usgs data")
