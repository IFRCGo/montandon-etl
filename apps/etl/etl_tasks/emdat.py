from celery import chain, shared_task

from apps.etl.extraction.sources.emdat.extract import (
    extract_emdat_historical_data,
    extract_emdat_latest_data,
)
from apps.etl.transform.sources.emdat import transform_emdat_data


@shared_task
def ext_and_transform_emdat_historical_data(**kwargs):
    chain(extract_emdat_historical_data.s(), transform_emdat_data.s()).apply_async()


@shared_task
def ext_and_transform_emdat_latest_data(**kwargs):
    chain(extract_emdat_latest_data.s(), transform_emdat_data.s()).apply_async()
