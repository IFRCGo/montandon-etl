import uuid

from celery import shared_task
from celery.utils.log import get_task_logger

from apps.etl.loaders import send_post_request_to_stac_api

logger = get_task_logger(__name__)


@shared_task
def load_glide_data(data):
    collection_id = "collection"
    for obj in data["data"]:
        if "properties" not in obj:
            obj["properties"] = {}
        obj["properties"]["monty:etl_id"] = str(uuid.uuid4())

        send_post_request_to_stac_api.delay(obj, f"{collection_id}")

    logger.info("Glide Data loaded successfully")
