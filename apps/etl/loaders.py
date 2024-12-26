import requests
import time
from celery import chain, shared_task
from celery.result import AsyncResult


def send_post_request(result, collection_id):
    try:
        url = f"http://montandon-eoapi-stage.ifrc.org/stac/collections/{collection_id}/items"
        response = requests.post(
            url,
            json=result,  # Send result as JSON payload
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()  # Raise an exception for HTTP errors
        print(f"POST Response for {collection_id}:", response.status_code, response.text)
    except requests.exceptions.RequestException as e:
        print(f"Error posting data for {collection_id}: {e}")


@shared_task
def finalize_all_tasks(event_result_id, geo_result_id, impact_result_id):
    while True:
        result = AsyncResult(event_result_id)
        if result.state == "SUCCESS":
            event_result = result.result
            break
        elif result.state == "FAILURE":
            raise Exception(f"Fetching event data failed with error: {result.result}")
        time.sleep(1)

    event_response = send_post_request(event_result, "test-collection")

    while True:
        result = AsyncResult(geo_result_id)
        if result.state == "SUCCESS":
            hazard_result = result.result
            break
        elif result.state == "FAILURE":
            raise Exception(f"Fetching hazard data failed with error: {result.result}")
        time.sleep(1)
    hazard_response = send_post_request(hazard_result, "test-collection")

    while True:
        result = AsyncResult(impact_result_id)
        if result.state == "SUCCESS":
            # Fetch the output of event task
            impact_result = result.result
            break
        elif result.state == "FAILURE":
            raise Exception(f"Fetching impact data failed with error: {result.result}")
        time.sleep(1)
    impact_response = send_post_request(impact_result, "test-collection")

    return "Data loaded successfully"
