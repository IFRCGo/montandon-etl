import uuid
import requests

from celery.utils.log import get_task_logger

from apps.etl.models import GlideTransformation, LoadStatus

logger = get_task_logger(__name__)


def send_post_request_to_stac_api(result, collection_id):
    try:
        # url = f"http://montandon-eoapi-stage.ifrc.org/stac/collections/{collection_id}/items"
        url = f"https://montandon-eoapi-1.ifrc-go.dev.togglecorp.com/stac/collections/{collection_id}/items"

        response = requests.post(
            url, json=result, headers={"Content-Type": "application/json"}  # Send result as JSON payload
        )
        response.raise_for_status()  # Raise an exception for HTTP errors
        print(f"POST Response for {collection_id}:", response.status_code, response.text)
        return response
    except requests.exceptions.RequestException as e:
        print(f"Error posting data for {collection_id}: {e}")


def load_data():
    """Load Gdacs data into STAC api."""
    logger.info("Loading data into Stac")

    transformed_items = GlideTransformation.objects.filter(load_status=LoadStatus.PENDING)
    for item in transformed_items:
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

    logger.info("Loading data sucessfull")
