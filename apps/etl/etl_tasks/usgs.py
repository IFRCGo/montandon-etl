from celery import shared_task

from apps.etl.extraction.sources.usgs.extract import (
    import_hazard_data as import_usgs_data,
)


@shared_task
def import_usgs_hazard_data(**kwargs):
    import_usgs_data()
