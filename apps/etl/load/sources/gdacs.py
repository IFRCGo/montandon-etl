from celery import shared_task
from celery.utils.log import get_task_logger

from apps.etl.load.sources.base import send_post_request_to_stac_api
from apps.etl.models import GdacsTransformation

logger = get_task_logger(__name__)


@shared_task
def load_data():
    """Load Gdacs data into STAC api."""
    logger.info("Loading gdacs data into Stac")
    transformed_items = GdacsTransformation.objects.filter(load_status=GdacsTransformation.LoadStatus.PENDING)
    for item in transformed_items:
        item_type = item.item_type
        if item_type == GdacsTransformation.ItemType.IMPACT:
            items_to_load = item.data["data"]
            if not items_to_load == []:
                for imp_item in items_to_load:
                    response = send_post_request_to_stac_api.delay(imp_item.data["item"], f"{imp_item.data['collection_id']}")
                    if response and response.status_code == 200:
                        item.load_status = GdacsTransformation.LoadStatus.SUCCESS
                        item.save(update_fields=["load_status"])
        else:
            response = send_post_request_to_stac_api.delay(item.data["item"], f"{item.data['collection_id']}")
            if response and response.status_code == 200:
                item.load_status = GdacsTransformation.LoadStatus.SUCCESS
                item.save(update_fields=["load_status"])
    logger.info("Loading gdacs data sucessfull")
