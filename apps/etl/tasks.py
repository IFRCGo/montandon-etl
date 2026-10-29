import logging
from datetime import datetime, timedelta

from celery import shared_task
from django.core.management import call_command

from apps.etl.extraction.sources.gdacs.extract import GdacsExtraction
from apps.etl.extraction.sources.pdc.extract import PDCExtractionV2
from apps.etl.extraction.sources.usgs.extract import USGSExtraction
from apps.etl.models import ExtractionData
from apps.etl.mutations import source_extraction_map
from main.cache import CeleryLock, cache
from main.cronjobs import TimeConstants

logger = logging.getLogger(__name__)

PENDING_EXTRACTION_TRIGGER_LIMIT = 500
PENDING_EXTRACTION_QUEUED_KEY_PREFIX = "PENDING_EXTRACTION_QUEUED:"
# NOTE: Queued message expires with the redis key, so a message can't outlive the key and be queued twice
PENDING_EXTRACTION_MESSAGE_EXPIRE = 3 * TimeConstants.SECONDS_IN_A_DAY
# Key is set before the message is queued, so keep it slightly longer than the message
PENDING_EXTRACTION_QUEUED_EXPIRE = PENDING_EXTRACTION_MESSAGE_EXPIRE + TimeConstants.SECONDS_IN_A_MINUTE


@shared_task
def load_data():
    """Load the data to STAC eoAPI server"""
    with CeleryLock.redis_lock(CeleryLock.Key.LOAD_TO_STAC, lock_expire=TimeConstants.SECONDS_IN_THREE_HOURS) as acquired:
        if not acquired:
            logger.warning("Load to STAC server already running")
            return

        call_command("load_data_to_stac")


@shared_task
def trigger_pending_extraction() -> None:
    """Trigger pending extractions"""
    logger.info("Trigger pending extraction in process")

    two_weeks_ago = datetime.today() - timedelta(days=14)
    pending_extraction_objects = ExtractionData.objects.filter(
        status=ExtractionData.Status.PENDING, created_at__date__lte=two_weeks_ago
    ).order_by("id")

    queued_count = 0
    for obj in pending_extraction_objects.iterator():
        if queued_count >= PENDING_EXTRACTION_TRIGGER_LIMIT:
            break
        if obj.status == ExtractionData.Status.SUCCESS:
            continue
        # NOTE: Status stays PENDING until a worker picks up the task, so skip if already queued in the broker
        # cache.add fails if the key already exists
        if not cache.add(f"{PENDING_EXTRACTION_QUEUED_KEY_PREFIX}{obj.id}", 1, PENDING_EXTRACTION_QUEUED_EXPIRE):
            continue
        queued_count += 1
        extraction_class = source_extraction_map[obj.source]
        if extraction_class in [GdacsExtraction, USGSExtraction, PDCExtractionV2]:  # nested extraction
            extraction_class.retrigger(obj, expires=PENDING_EXTRACTION_MESSAGE_EXPIRE)
        else:
            extraction_class.task.apply_async(args=(obj.id,), expires=PENDING_EXTRACTION_MESSAGE_EXPIRE)


@shared_task
def celery_queue_uptime_check(queue: str):
    """Check the availability of the Queue"""
    logger.info("Celery Queue %s is consuming tasks.", queue)
