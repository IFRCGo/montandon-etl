import time
import uuid

import requests
from celery import chain, shared_task
from celery.result import AsyncResult
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


@shared_task(bind=True, autoretry_for=(requests.exceptions.RequestException,), retry_kwargs={"max_retries": 3})
def send_post_request_to_stac_api(self, result, collection_id):
    try:
        # url = f"http://montandon-eoapi-stage.ifrc.org/stac/collections/{collection_id}/items"
        url = f"https://montandon-eoapi-1.ifrc-go.dev.togglecorp.com/stac/collections/{collection_id}/items"

        response = requests.post(
            url, json=result, headers={"Content-Type": "application/json"}  # Send result as JSON payload
        )
        response.raise_for_status()  # Raise an exception for HTTP errors
        logger.info(f"POST Response for {collection_id}:", response.status_code, response.text)
    except requests.exceptions.RequestException as e:
        logger.info(f"Error posting data for {collection_id}: {e}")


@shared_task(bind=True)
def process_load_data(self, task_id, task_name):
    while True:
        result = AsyncResult(task_id)
        if result.state == "SUCCESS":
            result = result.result
            break
        elif result.state == "FAILURE":
            raise Exception(f"Fetching {task_name} data failed with error: {result.result}")
        time.sleep(2)

    if not result == [] or {}:
        if "properties" not in result:
            result["properties"] = {}
        result["properties"]["monty:etl_id"] = str(uuid.uuid4())
        # result["id"] = f"{task_name}-{uuid.uuid4()}"  # Done for testing purpose to make id unique.

        send_post_request_to_stac_api.delay(result, f"{task_name}")

    return "Data loaded successfully"


@shared_task(bind=True)
def load_data(self, event_result_id, geo_result_id, impact_result_id):
    """Load data by chaining tasks instead of blocking calls."""
    try:
        # Create a chain of tasks for processing and posting data
        chain(
            process_load_data.si(event_result_id, "gdacs-events"),
            process_load_data.si(geo_result_id, "gdacs-hazards"),
            process_load_data.si(impact_result_id, "gdacs-impacts"),
        )()
        return "Data loading process started successfully."
    except Exception as e:
        logger.error(f"Error loading data: {e}")
        raise
