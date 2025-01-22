from celery import chain, shared_task

from apps.etl.extraction.sources.noaa_IBTrACS.extract import (
    import_hazard_data as import_noaa_data,
)
from apps.etl.transform.sources.noaa import transform_event_data


@shared_task
def import_noaa_hazard_data(**kwargs):
    # exp_id = import_noaa_data()

    transform_event_data(25)
