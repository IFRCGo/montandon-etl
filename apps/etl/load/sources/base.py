import urllib.parse

import requests
from celery.utils.log import get_task_logger

from apps.etl.models import PyStacLoadData
from apps.etl.transform.sources.handler import ITEM_TYPE_COLLECTION_ID_MAP
from main.configs import etl_config
from main.logging import log_extra_response
from main.managers import BulkUpdateManager

logger = get_task_logger(__name__)


HEADERS = {"Content-Type": "application/json"}


def load_collections(*, eoapi_domain: str) -> bool:
    """
    Create missing collections in eoAPI
    """
    logger.info("Sync collections")

    url = f"{eoapi_domain}/stac/collections"
    response = requests.get(url, headers=HEADERS)
    try:
        response.raise_for_status()

        # FIXME: Make sure ITEM_TYPE_COLLECTION_ID_MAP is using ref from pystac
        existing_collections = {
            collection["id"]
            for collection in response.json()["collections"]
            if collection["id"] in ITEM_TYPE_COLLECTION_ID_MAP
        }
        collections_to_add = set(ITEM_TYPE_COLLECTION_ID_MAP.keys()).difference(existing_collections)

        for collection_id in collections_to_add:
            response = requests.get(
                url,
                headers=HEADERS,
                json={
                    "id": collection_id,
                },
            )
            response.raise_for_status()
            logger.info(f"Successfully created collection id: {collection_id}")

        return True
    except Exception:
        logger.error("Failed to load collections", exc_info=True)
    return False


def send_post_request_to_stac_api(
    *,
    bulk_mgr: BulkUpdateManager,
    eoapi_domain: str,
    py_stac_obj: PyStacLoadData,
    to_update: bool = False,
):
    url = urllib.parse.urljoin(
        eoapi_domain,
        f"/stac/collections/{py_stac_obj.collection_id}/items",
    )

    if to_update:
        update_url = f"{url}/{py_stac_obj.item['id']}/"
        response = requests.put(update_url, headers=HEADERS, json=py_stac_obj.item)
    else:
        response = requests.post(url, headers=HEADERS, json=py_stac_obj.item)

    load_status = None
    # Success (OK, Created, Accepted)
    if response.status_code in [200, 201, 202]:
        load_status = PyStacLoadData.LoadStatus.SUCCESS
        logger.info(f"Successfully loaded item {py_stac_obj.id}")
    # Client Error (400 – 499)
    else:
        if response.status_code == 409 and to_update is False:  # ConflictError
            return send_post_request_to_stac_api(
                bulk_mgr=bulk_mgr,
                eoapi_domain=eoapi_domain,
                py_stac_obj=py_stac_obj,
                to_update=True,
            )

        if 400 <= response.status_code <= 499:
            load_status = PyStacLoadData.LoadStatus.FAILED
        logger.warning(
            f"Fail to load item {py_stac_obj.id}",
            extra=log_extra_response(response=response),
        )

    if load_status is not None:
        bulk_mgr.add(
            PyStacLoadData(
                id=py_stac_obj.id,
                load_status=load_status,
            ),
        )


def load_data(limit: int = 5000):
    """Load data into STAC"""
    logger.info("Loading data start")

    eoapi_domain = etl_config.EOAPI_DOMAIN
    if eoapi_domain is None:
        logger.warning(f"EOAPI_DOMAIN is not defined. {eoapi_domain}.. Skipping...")
        return

    if not load_collections(eoapi_domain=eoapi_domain):
        return

    pending_py_stac_qs = PyStacLoadData.objects.filter(load_status=PyStacLoadData.LoadStatus.PENDING)

    bulk_mgr = BulkUpdateManager(["load_status"], chunk_size=500)
    for py_stac_obj in pending_py_stac_qs.all()[:limit]:
        try:
            # TODO: Send in bulk - https://stac-utils.github.io/stac-fastapi/api/stac_fastapi/extensions/third_party/
            send_post_request_to_stac_api(
                bulk_mgr=bulk_mgr,
                eoapi_domain=eoapi_domain,
                py_stac_obj=py_stac_obj,
            )
        except Exception:
            logger.error("Error sending data to eoAPI", exc_info=True)
            # Something must be broken in eoAPI, let's try in another run
            break

    bulk_mgr.done()

    logger.info(f"Loading data stop: {bulk_mgr.summary()}")
