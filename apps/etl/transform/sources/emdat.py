import json
import logging
import uuid

from celery import shared_task
from django.conf import settings
from pystac_monty.geocoding import GAULGeocoder
from pystac_monty.sources.emdat import EMDATDataSource, EMDATTransformer

from apps.etl.models import ExtractionData, PyStacLoadData, Transform
from apps.etl.utils import read_file_data
from main.managers import BulkCreateManager

logger = logging.getLogger(__name__)

collection_and_item_type_map = {
    "emdat-events": PyStacLoadData.ItemType.EVENT,
    "emdat-hazards": PyStacLoadData.ItemType.HAZARD,
    "emdat-impacts": PyStacLoadData.ItemType.IMPACT,
}


@shared_task
def transform_emdat_data(extraction_id, **kwargs):
    """
    Transform extracted data from emdat graphql api to STAC item .
    """
    ext_instance = ExtractionData.objects.filter(id=extraction_id).first()
    if ext_instance and ext_instance.source_validation_status == ExtractionData.ValidationStatus.NO_DATA:
        logger.warning(
            "No data available",
        )
        return
    data = read_file_data(ext_instance.resp_data)
    json_data = json.loads(data)

    transform_data(
        ExtractionData.Source.EMDAT,
        EMDATTransformer,
        EMDATDataSource,
        extraction_id,
        json_data,
    )


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

    geocoder = GAULGeocoder(gpkg_path=None, service_base_url=settings.GEOCODER_URL)

    try:
        # Get transformer for each source and transform it to stac item..
        transformer = transformer(data=data_source(source_url=ext_instance.url, data=data), geocoder=geocoder)
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
