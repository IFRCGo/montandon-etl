from celery import shared_task
from django.conf import settings

from apps.etl.extraction.sources.pdc.extract import (
    PDCExtraction,
)


@shared_task
def extract_and_transform_pdc_data():
    data_url = f"{settings.PDC_BASE_URL}/hazards/t/json/get_active_hazards"
    header = {"Authorization": "Bearer {}".format(settings.PDC_AUTHORIZATION_KEY)}
    PDCExtraction.task.s(data_url, header).apply_async()
