import logging

from celery import chain, shared_task
from django.conf import settings

from apps.etl.extraction.sources.idu.extract import IDUExtraction
from apps.etl.transform.sources.idu import IDUTransformHandler

logger = logging.getLogger(__name__)


@shared_task
def extract_and_transform_idu_data(url):
    """Extract and Transform IDU data"""
    chain(
        IDUExtraction.task.s(url=url),
        IDUTransformHandler.task.s(),
    ).apply_async()


@shared_task
def ext_and_transform_idu_historical_data():
    """Extract and Transform IDU historical data"""
    url = f"{settings.IDMC_DATA_URL}/external-api/idus/all/"
    extract_and_transform_idu_data(url)


@shared_task
def ext_and_transform_idu_latest_data():
    """Extract and Transform IDU latest data"""
    url = f"{settings.IDMC_DATA_URL}/external-api/idus/last-180-days/"
    extract_and_transform_idu_data(url)
