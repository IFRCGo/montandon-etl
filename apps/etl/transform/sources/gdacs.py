import logging
import time
import uuid

from celery import shared_task
from celery.result import AsyncResult
from pystac_monty.sources.gdacs import (
    GDACSDataSource,
    GDACSDataSourceType,
    GDACSTransformer,
)

from apps.etl.models import ExtractionData, PyStacLoadData, Transform
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
        event_transform = Transform.objects.create(
            extraction=gdacs_instance,
            status=Transform.Status.SUCCESS,
        )
    except Exception as e:
        logger.error("Gdacs transformation failed", exc_info=True, extra={"extraction_id": gdacs_instance.id})
        Transform.objects.create(
            extraction=gdacs_instance,
            status=Transform.Status.FAILED,
        )
        raise e

    transformed_item_dict["properties"]["monty:etl_id"] = str(uuid.uuid4())
    PyStacLoadData.objects.create(
        transform_id=event_transform,
        item_type=PyStacLoadData.ItemType.EVENT,
        collection_id=transformed_event_item.collection_id,
        item=transformed_item_dict,
        load_status=PyStacLoadData.LoadStatus.PENDING,
    )

    logger.info("Trandformation ended for event data")


@shared_task
def transform_geo_data(geo_data, event_task_id):
    logger.info("Transformation started for hazard data")

    timeout = 60  # 1 minute
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
        transformed_hazard_item = transformer.make_hazard_event_item()
        transformed_item_dict = transformed_hazard_item.to_dict()

        hazard_transform = Transform.objects.create(
            extraction=gdacs_instance,
            status=Transform.Status.SUCCESS,
        )
    except Exception as e:
        logger.error("Gdacs transformation failed", exc_info=True, extra={"extraction_id": gdacs_instance.id})
        Transform.objects.create(
            extraction=gdacs_instance,
            status=Transform.Status.FAILED,
        )
        raise e

    transformed_item_dict["properties"]["monty:etl_id"] = str(uuid.uuid4())
    PyStacLoadData.objects.create(
        transform_id=hazard_transform,
        item_type=PyStacLoadData.ItemType.HAZARD,
        collection_id=transformed_hazard_item.collection_id,
        item=transformed_item_dict,
        load_status=PyStacLoadData.LoadStatus.PENDING,
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
        event_transform = Transform.objects.create(
            extraction=gdacs_instance,
            status=Transform.Status.SUCCESS,
        )
    except Exception as e:
        logger.error("Gdacs transformation failed", exc_info=True, extra={"extraction_id": gdacs_instance.id})
        Transform.objects.create(
            extraction=gdacs_instance,
            status=Transform.Status.FAILED,
        )
        raise e

    for item in transformed_impact_item:
        transformed_item_dict = item.to_dict()
        transformed_item_dict["properties"]["monty:etl_id"] = str(uuid.uuid4())
        PyStacLoadData.objects.create(
            extraction=gdacs_instance,
            transform_id=event_transform,
            item_type=PyStacLoadData.ItemType.IMPACT,
            collection_id=item.collection_id,
            item=transformed_item_dict,
            status=PyStacLoadData.LoadStatus.SUCCESS,
        )

    logger.info("Transformation ended for impact data")
