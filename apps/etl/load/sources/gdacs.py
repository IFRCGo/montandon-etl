import time
import uuid

from celery import chain, shared_task
from celery.result import AsyncResult
from celery.utils.log import get_task_logger
from etl.load.sources.base import send_post_request_to_stac_api

logger = get_task_logger(__name__)


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
