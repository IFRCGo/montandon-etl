import uuid

from celery.utils.log import get_task_logger

from apps.etl.load.sources.base import send_post_request_to_stac_api
from apps.etl.models import GdacsTransformation, ItemType, LoadStatus

logger = get_task_logger(__name__)


def load_gdacs_data():
    """Load Gdacs data into STAC api."""
    logger.info("Loading gdacs data into Stac")

    transformed_items = GdacsTransformation.objects.filter(load_status=LoadStatus.PENDING)
    for item in transformed_items:
        item_type = item.item_type
        # impact items comes in a list so need to handle in diffrent way
        if item_type == ItemType.IMPACT:
            items_to_load = item.data["data"]
            if not items_to_load == []:
                for imp_item in items_to_load:
                    # Add monty_etl_id into data to be loaded
                    item.data["item"]["properties"]["monty:etl_id"] = str(uuid.uuid4())

                    # TODO Remove this after sucessfull testing
                    # item.data["item"]["id"] = f"{item.data['collection_id']}-{uuid.uuid4()}"

                    response = send_post_request_to_stac_api(imp_item.data["item"], f"{imp_item.data['collection_id']}")
                    # Set the loading status of item.
                    if response and response.status_code == 200:
                        item.load_status = LoadStatus.SUCCESS
                    else:
                        item.load_status = LoadStatus.FAILED
                    item.save(update_fields=["load_status"])
        else:
            # Add monty_etl_id into data to be loaded
            item.data["item"]["properties"]["monty:etl_id"] = str(uuid.uuid4())

            # TODO Remove this after sucessfull testing
            # item.data["item"]["id"] = f"{item.data['collection_id']}-{uuid.uuid4()}"

            response = send_post_request_to_stac_api(item.data["item"], f"{item.data['collection_id']}")

            # Set the loading status of item.
            if response and response.status_code == 200:
                item.load_status = LoadStatus.SUCCESS
            else:
                item.load_status = LoadStatus.FAILED
            item.save(update_fields=["load_status"])

    logger.info("Loading gdacs data sucessfull")
