import json
import logging

from celery import shared_task
from django.db import transaction
from pystac_monty.sources.glide import GlideDataSource, GlideTransformer

from apps.etl.models import (
    ExtractionData,
    GlideTransformation,
    ItemType,
    TransformationStatus,
)

logger = logging.getLogger(__name__)

glide_item_type_map = {
    "glide-events": ItemType.EVENT,
    "glide-hazards": ItemType.HAZARD,
}


@shared_task
def transform_glide_event_data(data):
    logger.info("Transformation started for glide event data")
    glide_instance = ExtractionData.objects.get(id=data["extraction_id"])
    data_file_path = glide_instance.resp_data.path  # Absolute file path
    try:
        with open(data_file_path, "r") as file:
            data = json.loads(file.read())
    except FileNotFoundError:
        logger.error(f"File not found: {data_file_path}")
        raise
    except IOError as e:
        logger.error(f"I/O error while reading file: {str(e)}")
        raise

    if data["glideset"]:
        try:
            transformer = GlideTransformer(GlideDataSource(source_url=glide_instance.url, data=json.dumps(data)))
            with transaction.atomic():
                transformed_event_item = transformer.make_items()
                if not transformed_event_item == []:
                    for item in transformed_event_item:
                        print("Item", item.to_dict())
                        item_type = glide_item_type_map[item.collection_id]

                        GlideTransformation.objects.create(
                            extraction=glide_instance,
                            data={"item": item.to_dict(), "collection_id": item.collection_id},
                            item_type=item_type,
                            status=TransformationStatus.SUCCESS,
                            failed_reason="",
                        )
                        logger.info("Transformation ended for glide event data")
                    return {"data": [i.to_dict() for i in transformed_event_item]}
        except Exception as e:
            logger.info(f"Glide transformation failed for extraction id {glide_instance.id}, {e}")
            raise
