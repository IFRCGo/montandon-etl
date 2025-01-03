import logging

from celery import shared_task
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
    transformer = GlideTransformer([GlideDataSource(source_url=glide_instance.url, data=data)])

    try:
        transformed_event_item = transformer.make_items()
        item = {"data": [obj.to_dict() for obj in transformed_event_item]}

        GlideTransformation.objects.create(
            extraction=glide_instance,
            data=item,
            status=GdacsTransformation.TransformationStatus.SUCCESS,
            failed_reason="",
        )
    except Exception as e:
        GlideTransformation.objects.create(
            extraction=glide_instance,
            status=GdacsTransformation.TransformationStatus.FAILED,
            failed_reason=str(e),
        )

    if item:
        logger.info("Transformation ended for glide event data")
        return item
    else:
        raise Exception("Transformation failed for glide. Check logs for details.")
