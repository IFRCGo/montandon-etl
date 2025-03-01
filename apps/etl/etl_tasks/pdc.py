from celery import shared_task

from apps.etl.extraction.sources.pdc.extract import (
    get_hazard_details,
    import_hazard_data,
)


@shared_task
def extract_and_transform_pdc_data():
    extraction_id = import_hazard_data()
    get_hazard_details(extraction_id)
