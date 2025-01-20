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
from main.managers import BulkCreateManager

logger = logging.getLogger(__name__)


@shared_task
def transform_event_data(data):
    logger.info("Trandformation started for event data")

    gdacs_instance = ExtractionData.objects.get(id=data["extraction_id"])
    data = read_file_data(gdacs_instance.resp_data)

    transform_obj = Transform.objects.create(
        extraction=gdacs_instance,
        status=Transform.Status.PENDING,
    )

    try:
        transformer = GDACSTransformer(
            [GDACSDataSource(type=GDACSDataSourceType.EVENT, source_url=gdacs_instance.url, data=data)]
        )
        transformed_event_item = transformer.make_source_event_item()
        transformed_item_dict = transformed_event_item.to_dict()

        transform_obj.status = Transform.Status.SUCCESS
        transform_obj.save(update_fields=["status"])
    except Exception as e:
        logger.error("Gdacs transformation failed", exc_info=True, extra={"extraction_id": gdacs_instance.id})

        transform_obj.status = Transform.Status.FAILED
        transform_obj.save(update_fields=["status"])
        raise e

    transformed_item_dict["properties"]["monty:etl_id"] = str(uuid.uuid4())
    PyStacLoadData.objects.create(
        transform_id=transform_obj,
        item_type=PyStacLoadData.ItemType.EVENT,
        collection_id=transformed_event_item.collection_id,
        item=transformed_item_dict,
        load_status=PyStacLoadData.LoadStatus.PENDING,
    )

    transform_obj.is_loaded = True
    transform_obj.save(update_fields=["is_loaded"])

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
    transform_obj = Transform.objects.create(
        extraction=gdacs_instance,
        status=Transform.Status.PENDING,
    )

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

        transform_obj.status = Transform.Status.SUCCESS
        transform_obj.save(update_fields=["status"])

    except Exception as e:
        logger.error("Gdacs transformation failed", exc_info=True, extra={"extraction_id": gdacs_instance.id})

        transform_obj.status = Transform.Status.FAILED
        transform_obj.save(update_fields=["status"])
        raise e

    transformed_item_dict["properties"]["monty:etl_id"] = str(uuid.uuid4())
    PyStacLoadData.objects.create(
        transform_id=transform_obj,
        item_type=PyStacLoadData.ItemType.HAZARD,
        collection_id=transformed_hazard_item.collection_id,
        item=transformed_item_dict,
        load_status=PyStacLoadData.LoadStatus.PENDING,
    )
    transform_obj.is_loaded = True
    transform_obj.save(update_fields=["is_loaded"])

    logger.info("Transformation ended for hazard data")


@shared_task
def transform_impact_data(event_data):
    logger.info("Transformation started for impact data")

    gdacs_instance = ExtractionData.objects.get(id=event_data["extraction_id"])
    data = read_file_data(gdacs_instance.resp_data)

    transform_obj = Transform.objects.create(
        extraction=gdacs_instance,
        status=Transform.Status.PENDING,
    )

    bulk_mgr = BulkCreateManager(chunk_size=1000)
    try:
        transformer = GDACSTransformer(
            [GDACSDataSource(type=GDACSDataSourceType.EVENT, source_url=gdacs_instance.url, data=data)]
        )
        transformed_impact_item = transformer.make_impact_items()

        transform_obj.status = Transform.Status.SUCCESS
        transform_obj.save(update_fields=["status"])
    except Exception as e:
        logger.error("Gdacs transformation failed", exc_info=True, extra={"extraction_id": gdacs_instance.id})

        transform_obj.status = Transform.Status.FAILED
        transform_obj.save(update_fields=["status"])
        raise e

    for item in transformed_impact_item:
        transformed_item_dict = item.to_dict()
        transformed_item_dict["properties"]["monty:etl_id"] = str(uuid.uuid4())
        bulk_mgr.add(
            PyStacLoadData(
                transform_id=transform_obj,
                item_type=PyStacLoadData.ItemType.IMPACT,
                collection_id=item.collection_id,
                item=transformed_item_dict,
                status=PyStacLoadData.LoadStatus.PENDING,
            )
        )

    bulk_mgr.done()

    transform_obj.is_loaded = True
    transform_obj.save(update_fields=["is_loaded"])

    logger.info("Transformation ended for impact data")
