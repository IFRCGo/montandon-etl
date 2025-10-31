import logging
from datetime import datetime, timedelta

from celery import shared_task
from django.core.management import call_command

from apps.etl.extraction.sources.gdacs.extract import GdacsExtraction
from apps.etl.extraction.sources.pdc.extract import PDCExtractionV2
from apps.etl.extraction.sources.usgs.extract import USGSExtraction
from apps.etl.models import ExtractionData
from apps.etl.mutations import source_extraction_map
from main.cache import CeleryLock
from main.cronjobs import TimeConstants

logger = logging.getLogger(__name__)


@shared_task
def load_data():
    """Load the data to STAC eoAPI server"""
    with CeleryLock.redis_lock(CeleryLock.Key.LOAD_TO_STAC, lock_expire=TimeConstants.SECONDS_IN_SIX_HOURS) as acquired:
        if not acquired:
            logger.warning("Load to STAC server already running")
            return

        call_command("load_data_to_stac")


@shared_task
def trigger_pending_extraction() -> None:
    """Trigger pending extractions"""
    logger.info("Trigger pending extraction in process")

    two_days_ago = datetime.today() - timedelta(days=2)
    pending_extraction_objects = ExtractionData.objects.filter(
        status=ExtractionData.Status.PENDING, created_at__date__lte=two_days_ago
    )[:500]

    for obj in pending_extraction_objects:
        if obj.status == ExtractionData.Status.SUCCESS:
            continue
        extraction_class = source_extraction_map[obj.source]
        if extraction_class in [GdacsExtraction, USGSExtraction, PDCExtractionV2]:  # nested extraction
            extraction_class.retrigger(obj)
        else:
            extraction_class.task.delay(obj.id)


@shared_task
def celery_queue_uptime_check(queue: str):
    """Check the availability of the Queue"""
    logger.info("Celery Queue %s is consuming tasks.", queue)
