import logging
import time

from celery import shared_task
from celery.result import AsyncResult
from pystac_monty.sources.gdacs import (
    GDACSDataSource,
    GDACSDataSourceType,
    GDACSTransformer,
)

from apps.etl.models import (
    ExtractionData,
    GdacsTransformation,
    Transformation,
    STACItem,
    ItemType,
    TransformationStatus,
)
from apps.etl.utils import read_file_data

logger = logging.getLogger(__name__)


@shared_task
def transform_event_data(data):
    logger.info("Trandformation started for event data")

    gdacs_instance = ExtractionData.objects.get(id=data["extraction_id"])
    data = read_file_data(gdacs_instance.resp_data)

    try:
        transformer = GDACSTransformer(
            [GDACSDataSource(type=GDACSDataSourceType.EVENT, source_url=gdacs_instance.url, data=data)]
        )
        transformed_event_item = transformer.make_source_event_item()
        transformed_item_dict = transformed_event_item.to_dict()
        Transformation.objects.create(
            extraction=gdacs_instance,
            data=transformed_item_dict,
            status=TransformationStatus.SUCCESS,
        )
    except Exception as e:
        logger.error(
            "Gdacs transformation failed",
            exc_info=True,
            extra={"extraction_id": gdacs_instance.id}
        )
        Transformation.objects.create(
            extraction=gdacs_instance,
            status=TransformationStatus.FAILED,
        )
        raise e

    STACItem.objects.create(
        extraction=gdacs_instance,
        item_type=ItemType.EVENT,
        collection_id="gdacs-events",
        data=transformed_item_dict,
        load_status=STACItem.LoadStatus.PENDING,
    )

    logger.info("Trandformation ended for event data")


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

    data = read_file_data(gdacs_instance.resp_data)

    try:
        transformer = GDACSTransformer(
            [
                GDACSDataSource(
                    type=GDACSDataSourceType.EVENT, source_url=gdacs_instance.url, data=event_data["extracted_data"]
                ),
                GDACSDataSource(type=GDACSDataSourceType.GEOMETRY, source_url=gdacs_instance.url, data=data),
            ]
        )
        transformed_item_dict = transformer.make_hazard_event_item()

        Transformation.objects.create(
            extraction=gdacs_instance,
            data=transformed_item_dict,
            status=TransformationStatus.SUCCESS,
        )
    except Exception as e:
        logger.error(
            "Gdacs transformation failed",
            exc_info=True,
            extra={"extraction_id": gdacs_instance.id}
        )
        Transformation.objects.create(
            extraction=gdacs_instance,
            status=TransformationStatus.FAILED,
        )
        raise e

    STACItem.objects.create(
        extraction=gdacs_instance,
        item_type=ItemType.HAZARD,
        collection_id="gdacs-hazards",
        data=transformed_item_dict,
        load_status=STACItem.LoadStatus.PENDING,
    )

    logger.info("Transformation ended for hazard data")


@shared_task
def transform_impact_data(event_data):
    logger.info("Transformation started for impact data")

    gdacs_instance = ExtractionData.objects.get(id=event_data["extraction_id"])
    data = read_file_data(gdacs_instance.resp_data)

    try:
        transformer = GDACSTransformer(
            [GDACSDataSource(type=GDACSDataSourceType.EVENT, source_url=gdacs_instance.url, data=data)]
        )
        transformed_impact_item = transformer.make_impact_items()
        Transformation.objects.create(
            extraction=gdacs_instance,
            data={"items": [item.to_dict() for item in transformed_impact_item]},
            status=TransformationStatus.SUCCESS,
        )
    except Exception as e:
        logger.error(
            "Gdacs transformation failed",
            exc_info=True,
            extra={"extraction_id": gdacs_instance.id}
        )
        Transformation.objects.create(
            extraction=gdacs_instance,
            status=TransformationStatus.FAILED,
        )
        raise e

    for item in transformed_impact_item:
        STACItem.objects.create(
            extraction=gdacs_instance,
            item_type=ItemType.IMPACT,
            collection_id="gdacs-impacts",
            data=item.to_dict(),
            status=STACItem.LoadStatus.SUCCESS,
        )

    logger.info("Transformation ended for impact data")
