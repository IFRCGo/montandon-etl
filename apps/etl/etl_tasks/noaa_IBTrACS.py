import logging
from urllib.parse import urljoin

from celery import chain, shared_task

from apps.etl.extraction.sources.noaa_IBTrACS.extract import IBTrACSExtraction
from apps.etl.transform.sources.noaa_ibtracs import IbtracsTransformHandler
from main.configs import etl_config

logger = logging.getLogger(__name__)


@shared_task
def extract_and_transform_ibtracs_data(url):
    chain(
        IBTrACSExtraction.task.s(url),
        IbtracsTransformHandler.task.s(),
    ).apply_async()


def get_url(path):
    return urljoin(
        (
            f"{etl_config.IBTRACS_DATA_URL}"
            "/data/international-best-track-archive-for-climate-stewardship-ibtracs/v04r01/access/csv"
        ),
        path,
    )


@shared_task
def ext_and_transform_ibtracs_historical_data():
    url = get_url("/ibtracs.ALL.list.v04r01.csv")
    extract_and_transform_ibtracs_data(url)


@shared_task
def ext_and_transform_ibtracs_latest_data():
    url = get_url("/ibtracs.ACTIVE.list.v04r01.csv")
    extract_and_transform_ibtracs_data(url)
