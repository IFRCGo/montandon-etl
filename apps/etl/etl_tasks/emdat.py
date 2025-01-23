from celery import shared_task

from apps.etl.extraction.sources.emdat.extract import import_hazard_data
from apps.etl.transform.sources.emdat import transform_emdat_data


@shared_task
def extract_and_transform_emdat_data(**kwargs):
    # Extract the data from emdat
    extraction_id = import_hazard_data()

    # Transform the data from emdat
    transform_emdat_data(extraction_id)
