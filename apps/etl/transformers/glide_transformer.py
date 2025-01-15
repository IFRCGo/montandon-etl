import logging

from celery import shared_task
from django.db import transaction
from pystac_monty.sources.glide import GlideDataSource, GlideTransformer

from apps.etl.models import ExtractionData, GdacsTransformation, GlideTransformation

logger = logging.getLogger(__name__)


@shared_task
def transform_glide_event_data(data):
    logger.info("Transformation started for glide event data")
    glide_instance = ExtractionData.objects.get(id=data["extraction_id"])
    data_file_path = glide_instance.resp_data.path  # Absolute file path
    try:
        with open(data_file_path, "r") as file:
            data = file.read()
    except FileNotFoundError:
        logger.error(f"File not found: {data_file_path}")
        raise
    except IOError as e:
        logger.error(f"I/O error while reading file: {str(e)}")
        raise

    transformer = GlideTransformer(GlideDataSource(source_url=glide_instance.url, data=data))

    try:
        with transaction.atomic():
            transformed_event_item = transformer.make_items()
            if not transformed_event_item == []:
                for item in transformed_event_item:

                    GlideTransformation.objects.create(
                        extraction=glide_instance,
                        data=item.to_dict(),
                        status=GdacsTransformation.TransformationStatus.SUCCESS,
                        failed_reason="",
                    )
                    logger.info("Transformation ended for glide event data")
                return {"data": [i.to_dict() for i in transformed_event_item]}
    except Exception as e:
        logger.info(f"Glide transformation failed for extraction id {glide_instance.id}")
        GlideTransformation.objects.create(
            extraction=glide_instance,
            status=GdacsTransformation.TransformationStatus.FAILED,
            failed_reason=str(e),
        )
        raise
