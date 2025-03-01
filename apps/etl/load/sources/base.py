import urllib.parse

import requests
from celery.utils.log import get_task_logger
from django.conf import settings
from django.core.management.base import BaseCommand

from apps.etl.models import PyStacLoadData
from main.managers import BulkUpdateManager

logger = get_task_logger(__name__)


def send_post_request_to_stac_api(result, collection_id):
    try:
        url = urllib.parse.urljoin(
            settings.EOAPI_DOMAIN,
            f"/stac/collections/{collection_id}/items",
        )

        response = requests.post(url, json=result, headers={"Content-Type": "application/json"})
        response.raise_for_status()
        return response
    except requests.exceptions.RequestException as e:
        print(f"Error posting data for {collection_id}: {e}")


def load_data(django_command: BaseCommand | None = None):
    """Load data into STAC"""
    logger.info("Loading data into Stac")

    transformed_items = PyStacLoadData.objects.exclude(load_status=PyStacLoadData.LoadStatus.SUCCESS)

    bulk_mgr = BulkUpdateManager(["load_status"], chunk_size=1000)
    for item in transformed_items.iterator():
        # TODO Remove this after sucessfull testing
        # import uuid
        # item.item["id"] = f"{item.item['collection']}-{uuid.uuid4()}"

        response = send_post_request_to_stac_api(item.item, f"{item.collection_id}")

        # Set the loading status of item.
        if response and response.status_code == 200:
            bulk_mgr.add(
                PyStacLoadData(
                    id=item.id,
                    load_status=PyStacLoadData.LoadStatus.SUCCESS,
                ),
            )
            if django_command is not None:
                django_command.stdout.write(django_command.style.SUCCESS(f"Successfully loaded item {item.id}"))
        else:
            bulk_mgr.add(
                PyStacLoadData(
                    id=item.id,
                    load_status=PyStacLoadData.LoadStatus.FAILED,
                ),
            )

            if django_command is not None:
                django_command.stdout.write(django_command.style.ERROR(f"Fail to load item {item.id}"))

    bulk_mgr.done()

    logger.info("Loading data sucessfull")
