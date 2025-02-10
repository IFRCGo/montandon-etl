from celery import shared_task

from apps.etl.extraction.sources.usgs.extract import (
    import_hazard_data as extraction_and_transform_usgs_data,
)


@shared_task
def import_and_transform_usgs_data(**kwargs):
    extraction_and_transform_usgs_data()
