from celery import chain, shared_task

from apps.etl.extraction.sources.pdc.extract import (
    get_hazard_details,
    import_hazard_data,
)


@shared_task
def extract_and_transform_pdc_data():
    chain(import_hazard_data.s(), get_hazard_details.s()).apply_async()
