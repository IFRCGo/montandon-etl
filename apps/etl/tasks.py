import logging

from celery import shared_task
from django.core.management import call_command

from apps.etl.extraction.sources.gdacs.extract import GdacsExtraction
from apps.etl.extraction.sources.pdc.extract import PDCExtractionV2
from apps.etl.extraction.sources.usgs.extract import USGSExtraction
from apps.etl.models import ExtractionData
from apps.etl.mutations import source_extraction_map

logger = logging.getLogger(__name__)


@shared_task
def load_data():
    call_command("load_data_to_stac")


@shared_task
def trigger_pending_extraction() -> None:
    logger.info("Trigger pending extraction in process")

    pending_extraction_objects = ExtractionData.objects.filter(status=ExtractionData.Status.PENDING)

    for obj in pending_extraction_objects:
        if obj.status == ExtractionData.Status.SUCCESS:
            continue
        extraction_class = source_extraction_map[obj.source]
        if extraction_class in [GdacsExtraction, USGSExtraction, PDCExtractionV2]:  # nested extraction
            extraction_class.retrigger(obj)
        else:
            extraction_class.task.delay(obj.id)
