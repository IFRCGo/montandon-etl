import logging

from celery import chain, shared_task
from django.conf import settings

from apps.etl.extraction.sources.idu.extract import IDUExtraction
from apps.etl.transform.sources.idu import IDUTransformHandler

logger = logging.getLogger(__name__)

HISTORICAL_DATA_URL = f"{settings.IDU_DATA_URL}/external-api/idus/idus_all_retrieve"
LATEST_DATA_URL = f"{settings.IDU_DATA_URL}/external-api/idus/last-180-days/"


@shared_task
def extract_and_transform_idu_data(url):

    chain(
        IDUExtraction.handle_extraction.s(url=url),
        IDUTransformHandler.task.s(),
    ).apply_async()


@shared_task
def ext_and_transform_idu_historical_data():
    extract_and_transform_idu_data(HISTORICAL_DATA_URL)


@shared_task
def ext_and_transform_idu_latest_data():
    extract_and_transform_idu_data(LATEST_DATA_URL)
