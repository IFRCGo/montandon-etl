from celery import shared_task

from apps.etl.extraction.sources.emdat.extract import (
    extract_emdat_historical_data,
    extract_emdat_latest_data,
)
from apps.etl.transform.sources.emdat import transform_emdat_data


@shared_task
def ext_and_transform_emdat_historical_data(**kwargs):
    # Extract the data from emdat
    extraction_id = extract_emdat_historical_data()

    # Transform the data from emdat
    transform_emdat_data(extraction_id)


@shared_task
def ext_and_transform_emdat_latest_data(**kwargs):
    # Extract the data from emdat
    extraction_id = extract_emdat_latest_data()

    # Transform the data from emdat
    transform_emdat_data(extraction_id)
