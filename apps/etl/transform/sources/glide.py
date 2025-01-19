import json
import logging

from celery import shared_task
from pystac_monty.sources.glide import GlideDataSource, GlideTransformer

from apps.etl.models import (
    ExtractionData,
    GlideTransformation,
    ItemType,
    Transformation,
    STACItem,
    TransformationStatus,
)
from apps.etl.utils import read_file_data

logger = logging.getLogger(__name__)

glide_item_type_map = {
    "glide-events": ItemType.EVENT,
    "glide-hazards": ItemType.HAZARD,
}


@shared_task
def transform_glide_event_data(data):
    logger.info("Transformation started for glide event data")
    glide_instance = ExtractionData.objects.get(id=data["extraction_id"])
    data = json.loads(read_file_data(glide_instance.resp_data))

    if data["glideset"]:
        try:
            transformer = GlideTransformer(GlideDataSource(source_url=glide_instance.url, data=json.dumps(data)))
            transformed_event_items = transformer.make_items()
            Transformation.objects.create(
                extraction=glide_instance,
                data={"items": [item.to_dict() for item in transformed_event_items]},
                status=TransformationStatus.SUCCESS,
            )
        except Exception as e:
            logger.error(
                "Glide transformation failed",
                exc_info=True,
                extra={"extraction_id": glide_instance.id}
            )
            Transformation.objects.create(
                extraction=glide_instance,
                status=TransformationStatus.FAILED,
            )
            raise e

        if not transformed_event_item == []:
            for item in transformed_event_item:
                item_type = glide_item_type_map[item.collection_id]

                STACItem.objects.objects.create(
                    extraction=glide_instance,
                    data=item.to_dict(),
                    collection_id=item.collection_id,
                    item_type=item_type,
                    load_status=STACItem.LoadStatus.PENDING,
                )
        logger.info("Transformation ended for glide event data")
