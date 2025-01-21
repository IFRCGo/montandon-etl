from celery import chain, shared_task

from apps.etl.extraction.sources.noaa_IBTrACS.extract import (
    import_hazard_data as import_noaa_data,
)

@shared_task
def import_noaa_hazard_data(**kwargs):
    import_noaa_data() 