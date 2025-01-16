import requests
from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


@shared_task(bind=True, autoretry_for=(requests.exceptions.RequestException,), retry_kwargs={"max_retries": 3})
def send_post_request_to_stac_api(result, collection_id):
    try:
        # url = f"http://montandon-eoapi-stage.ifrc.org/stac/collections/{collection_id}/items"
        url = f"https://montandon-eoapi-1.ifrc-go.dev.togglecorp.com/stac/collections/{collection_id}/items"

        response = requests.post(
            url, json=result, headers={"Content-Type": "application/json"}  # Send result as JSON payload
        )
        response.raise_for_status()  # Raise an exception for HTTP errors
        logger.info(f"POST Response for {collection_id}:", response.status_code, response.text)
        return response
    except requests.exceptions.RequestException as e:
        logger.info(f"Error posting data for {collection_id}: {e}")
