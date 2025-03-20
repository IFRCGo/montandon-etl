import logging

from celery import chain, shared_task
from django.conf import settings

from apps.etl.extraction.sources.noaa_IBTrACS.extract import IBTrACSExtraction
from apps.etl.transform.sources.noaa_ibtracs import IbtracsTransformHandler

logger = logging.getLogger(__name__)


@shared_task
def extract_and_transform_ibtracs_data(url):
    chain(
        IBTrACSExtraction.task.s(url),
        IbtracsTransformHandler.task.s(),
    ).apply_async()


@shared_task
def ext_and_transform_ibtracs_historical_data():
    url = f"{settings.IBTRACS_DATA_URL}/ibtracs.ALL.list.v04r01.csv"
    extract_and_transform_ibtracs_data(url)


@shared_task
def ext_and_transform_ibtracs_latest_data():
    url = f"{settings.IBTRACS_DATA_URL}/ibtracs.ACTIVE.list.v04r01.csv"
    extract_and_transform_ibtracs_data(url)
