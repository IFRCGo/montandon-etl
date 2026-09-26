import logging
from datetime import datetime, timedelta

from celery import shared_task
from django.core.management import call_command
from django.db.models import Count

from apps.etl.extraction.sources.gdacs.extract import GdacsExtraction
from apps.etl.extraction.sources.pdc.extract import PDCExtractionV2
from apps.etl.extraction.sources.usgs.extract import USGSExtraction
from apps.etl.models import ExtractionData, PyStacLoadData, StatusSnapshot, Transform
from apps.etl.mutations import source_extraction_map
from main.cache import CeleryLock
from main.cronjobs import TimeConstants

logger = logging.getLogger(__name__)


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


@shared_task
def snapshot_status_counts():
    """Snapshot current status counts per source, for the dashboard's point-in-time trend chart"""
    lock_expire = TimeConstants.SECONDS_IN_HALF_DAY
    with CeleryLock.redis_lock(CeleryLock.Key.SNAPSHOT_STATUS_COUNTS, lock_expire=lock_expire) as acquired:
        if not acquired:
            logger.warning("Snapshot status counts already running")
            return

        resource_querysets = [
            (StatusSnapshot.ResourceType.EXTRACTION, ExtractionData.objects.values("source", "status"), "source"),
            (
                StatusSnapshot.ResourceType.TRANSFORM,
                Transform.objects.values("extraction__source", "status"),
                "extraction__source",
            ),
            (
                StatusSnapshot.ResourceType.PYSTAC,
                PyStacLoadData.objects.values("transform_id__extraction__source", "status"),
                "transform_id__extraction__source",
            ),
        ]

        snapshots = []
        for resource_type, qs, source_field in resource_querysets:
            for row in qs.annotate(count=Count("id")).order_by():
                snapshots.append(
                    StatusSnapshot(
                        resource_type=resource_type,
                        source=row[source_field],
                        status=row["status"],
                        count=row["count"],
                    )
                )

        StatusSnapshot.objects.bulk_create(snapshots)
        logger.info("Snapshot status counts done. %s rows created.", len(snapshots))
