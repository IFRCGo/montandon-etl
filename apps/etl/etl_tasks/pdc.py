from celery import shared_task
from django.conf import settings

from apps.etl.extraction.sources.pdc.extract import (
    PDCExtraction,
)


@shared_task
def extract_and_transform_pdc_data():
    data_url = f"{settings.PDC_BASE_URL}/hazards/t/json/get_active_hazards"
    PDCExtraction.task.s(data_url).apply_async()
