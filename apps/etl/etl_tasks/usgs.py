import logging
from datetime import datetime, timedelta

from celery import shared_task
from main.celery import CeleryQueue

from apps.etl.extraction.sources.usgs.extract import USGSExtraction, USGSExtractionMetadata, USGSExtractionMetadataType
from apps.etl.models import ExtractionData
from main.configs import etl_config
from datetime import date
logger = logging.getLogger(__name__)


# FIXME: This does not work if one of the system is down for more than a day
@shared_task
def ext_and_transform_usgs_latest_data():
    """Extract and Transform USGS latest data"""
    ext_object = (
        ExtractionData.objects.filter(
            source=ExtractionData.Source.USGS,
            status=ExtractionData.Status.SUCCESS,
            # FIXME: Why do we add filter that resp_data__isnull
            resp_data__isnull=False,
        )
        .order_by("-created_at")
        .first()
    )

    if ext_object:
        start_date = ext_object.created_at.date()
    else:
        start_date = etl_config.USGS_START_DATE

    url = f"{etl_config.USGS_DATA_URL}/fdsnws/event/1/query?format=geojson&starttime={start_date.strftime('%Y-%m-%d')}"

    USGSExtraction.init_extraction(
        metadata=USGSExtractionMetadata(
            url=url,
            type=USGSExtractionMetadataType.QUERY,
        ),
    )

@shared_task
def dispatch_usgs_historical_data():
    start_date = etl_config.USGS_START_DATE
    end_date = etl_config.USGS_END_DATE or datetime.now().date()

    total_days = (end_date - start_date).days
    chunk_size = total_days // 4

    date_chunks = [
        (start_date + timedelta(days=i * chunk_size),
         start_date + timedelta(days=(i + 1) * chunk_size) if i < 3 else end_date)
        for i in range(4)
    ]

    queues = [
        CeleryQueue.USGS_EXTRACTION_1,
        CeleryQueue.USGS_EXTRACTION_2,
        CeleryQueue.USGS_EXTRACTION_3,
        CeleryQueue.USGS_EXTRACTION_4,
    ]

    for (chunk_start, chunk_end), queue in zip(date_chunks, queues):
        ext_and_transform_usgs_historical_data.apply_async(
            args=[chunk_start, chunk_end, queue],
            queue=queue
        )


@shared_task
def ext_and_transform_usgs_historical_data(start_date: date, end_date: date, queue_name: str):
    """Extract and Transform USGS historical data for a given date range"""
    while start_date < end_date:
        next_date = min(start_date + timedelta(days=20), end_date)

        url = (
            f"{etl_config.USGS_DATA_URL}/fdsnws/event/1/query?format=geojson"
            f"&starttime={start_date.strftime('%Y-%m-%d')}"
            f"&endtime={next_date.strftime('%Y-%m-%d')}"
        )

        USGSExtraction.init_extraction(
            metadata=USGSExtractionMetadata(
                url=url,
                type=USGSExtractionMetadataType.QUERY,
            ),
            queue_name=queue_name,  # Optional: use the same as dispatch or recompute
        )

        start_date = next_date

    logger.info("USGS historical data extraction completed")

