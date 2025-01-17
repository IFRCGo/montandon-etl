import uuid

from celery.utils.log import get_task_logger

from apps.etl.load.sources.base import send_post_request_to_stac_api
from apps.etl.models import GlideTransformation, LoadStatus

logger = get_task_logger(__name__)


def load_glide_data():
    logger.info("Loading started for glide data")
    transformed_items = GlideTransformation.objects.filter(load_status=LoadStatus.PENDING)
    for item in transformed_items:
        if not item.data == []:
            # Add monty_etl_id into data to be loaded
            item.data["item"]["properties"]["monty:etl_id"] = str(uuid.uuid4())

            # TODO Remove this after successfull testing
            # item.data["item"]["id"] = f"{item.data['collection_id']}-{uuid.uuid4()}"

            response = send_post_request_to_stac_api(item.data["item"], f"{item.data['collection_id']}")

            # Set the loading status of item.
            if response and response.status_code == 200:
                item.load_status = LoadStatus.SUCCESS
            else:
                item.load_status = LoadStatus.FAILED
            item.save(update_fields=["load_status"])
    logger.info("Loading sucessfull for glide data")
