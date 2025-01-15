import logging
import time

from celery import shared_task
from celery.result import AsyncResult
from pystac_monty.sources.gdacs import (
    GDACSDataSource,
    GDACSDataSourceType,
    GDACSTransformer,
)

from apps.etl.models import ExtractionData, GdacsTransformation

logger = logging.getLogger(__name__)


@shared_task
def transform_event_data(data):
    logger.info("Trandformation started for event data")

    gdacs_instance = ExtractionData.objects.get(id=data["extraction_id"])

    data_file_path = gdacs_instance.resp_data.path  # Absolute file path

    try:
        with open(data_file_path, "r") as file:
            data = file.read()
    except FileNotFoundError:
        logger.error(f"File not found: {data_file_path}")
        raise
    except IOError as e:
        logger.error(f"I/O error while reading file: {str(e)}")
        raise

    transformer = GDACSTransformer(
        [GDACSDataSource(type=GDACSDataSourceType.EVENT, source_url=gdacs_instance.url, data=data)]
    )

    transformed_item_dict = {}
    try:
        transformed_event_item = transformer.make_source_event_item()
        transformed_item_dict = transformed_event_item.to_dict()

        GdacsTransformation.objects.create(
            extraction=gdacs_instance,
            item_type=GdacsTransformation.ItemType.EVENT,
            data=transformed_item_dict,
            status=GdacsTransformation.TransformationStatus.SUCCESS,
            failed_reason="",
        )
    except Exception as e:
        GdacsTransformation.objects.create(
            extraction=gdacs_instance,
            item_type=GdacsTransformation.ItemType.EVENT,
            status=GdacsTransformation.TransformationStatus.FAILED,
            failed_reason=str(e),
        )

    if transformed_item_dict:
        logger.info("Trandformation ended for event data")
        return transformed_item_dict
    else:
        raise Exception("Transformation failed. Check logs for details.")


@shared_task
def transform_geo_data(geo_data, event_task_id):
    logger.info("Transformation started for hazard data")

    timeout = 300  # 5 minutes
    start_time = time.time()
    while True:
        result = AsyncResult(event_task_id)
        if result.state == "SUCCESS":
            # Fetch the output of event task
            event_data = result.result
            break
        elif result.state == "FAILURE":
            raise Exception(f"Fetching event data failed with error: {result.result}")
        elif time.time() - start_time > timeout:
            raise TimeoutError("Fetching event data timed out.")
        time.sleep(1)

    gdacs_instance = ExtractionData.objects.get(id=geo_data["extraction_id"])
    data_file_path = gdacs_instance.resp_data.path  # Absolute file path

    try:
        with open(data_file_path, "r") as file:
            data = file.read()
    except FileNotFoundError:
        logger.error(f"File not found: {data_file_path}")
        raise
    except IOError as e:
        logger.error(f"I/O error while reading file: {str(e)}")
        raise

    transformer = GDACSTransformer(
        [
            GDACSDataSource(
                type=GDACSDataSourceType.EVENT, source_url=gdacs_instance.url, data=event_data["extracted_data"]
            ),
            GDACSDataSource(type=GDACSDataSourceType.GEOMETRY, source_url=gdacs_instance.url, data=data),
        ]
    )
    transformed_item_dict = {}
    try:
        transformed_geo_item = transformer.make_hazard_event_item()
        transformed_item_dict = transformed_geo_item.to_dict()

        GdacsTransformation.objects.create(
            extraction=gdacs_instance,
            item_type=GdacsTransformation.ItemType.HAZARD,
            data=transformed_item_dict,
            status=GdacsTransformation.TransformationStatus.SUCCESS,
            failed_reason="",
        )
    except Exception as e:
        GdacsTransformation.objects.create(
            extraction=gdacs_instance,
            item_type=GdacsTransformation.ItemType.HAZARD,
            status=GdacsTransformation.TransformationStatus.FAILED,
            failed_reason=str(e),
        )

    if transformed_item_dict:
        logger.info("Transformation ended for hazard data")
        return transformed_item_dict
    else:
        raise Exception("Transformation failed. Check logs for details.")


@shared_task
def transform_impact_data(event_data):
    logger.info("Transformation started for impact data")

    gdacs_instance = ExtractionData.objects.get(id=event_data["extraction_id"])
    data_file_path = gdacs_instance.resp_data.path  # Absolute file path
    try:
        with open(data_file_path, "r") as file:
            data = file.read()
    except FileNotFoundError:
        logger.error(f"File not found: {data_file_path}")
        raise
    except IOError as e:
        logger.error(f"I/O error while reading file: {str(e)}")
        raise
    transformer = GDACSTransformer(
        [GDACSDataSource(type=GDACSDataSourceType.EVENT, source_url=gdacs_instance.url, data=data)]
    )

    transformed_item_dict = {"data": []}
    try:
        transformed_impact_item = transformer.make_impact_items()
        transformed_item_dict = {"data": transformed_impact_item}

        GdacsTransformation.objects.create(
            extraction=gdacs_instance,
            item_type=GdacsTransformation.ItemType.IMPACT,
            data=transformed_item_dict,
            status=GdacsTransformation.TransformationStatus.SUCCESS,
            failed_reason="",
        )
    except Exception as e:
        GdacsTransformation.objects.create(
            extraction=gdacs_instance,
            item_type=GdacsTransformation.ItemType.IMPACT,
            status=GdacsTransformation.TransformationStatus.FAILED,
            failed_reason=str(e),
        )

    if transformed_item_dict:
        logger.info("Transformation ended for impact data")
        return transformed_item_dict
    else:
        raise Exception("Transformation failed. Check logs for details.")
