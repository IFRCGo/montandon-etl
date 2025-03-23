from celery import shared_task

from apps.etl.extraction.sources.pdc.extract import (
    PDCExtraction,
)
from main.configs import etl_config


@shared_task
def extract_and_transform_pdc_data():
    data_url = f"{etl_config.PDC_SENTRY_BASE_URL}/hp_srv/services/hazards/t/json/get_active_hazards"
    PDCExtraction.task.s(data_url).apply_async()
