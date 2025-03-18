import logging

from celery import chain, shared_task
from django.conf import settings

from apps.etl.extraction.sources.noaa_ibtracs.extract import IBTRACSExtraction
from apps.etl.transform.sources.noaa_ibtracs import IbtracsTransformHandler

HISTORICAL_DATA_URL = f"{settings.IBTRACS_DATA_URL}/ibtracs.ALL.list.v04r01.csv"
LATEST_DATA_URL = f"{settings.IBTRACS_DATA_URL}/ibtracs.ACTIVE.list.v04r01.csv"

logger = logging.getLogger(__name__)


@shared_task
def extract_and_transform_ibtracs_data(url):

    chain(
        IBTRACSExtraction.task.s(url),
        IbtracsTransformHandler.task.s(),
    ).apply_async()


@shared_task
def ext_and_transform_ibtracs_historical_data():
    chain(
        IBTRACSExtraction.task.s(LATEST_DATA_URL),
        IbtracsTransformHandler.task.s(),
    ).apply_async()


@shared_task
def ext_and_transform_ibtracs_latest_data():
    chain(
        IBTRACSExtraction.task.s(LATEST_DATA_URL),
        IbtracsTransformHandler.task.s(),
    ).apply_async()
