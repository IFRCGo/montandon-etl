import logging
from datetime import datetime, timedelta

from celery import shared_task

from apps.etl.extraction.sources.usgs.extract import USGSExtraction, USGSExtractionMetadata, USGSExtractionMetadataType
from apps.etl.models import ExtractionData
from main.configs import etl_config

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
def ext_and_transform_usgs_historical_data():
    """Extract and Transform USGS historical data"""
    start_date = etl_config.USGS_START_DATE
    end_date = etl_config.USGS_END_DATE or datetime.now().date

    while start_date.strftime("%Y-%m-%d") < end_date.strftime("%Y-%m-%d"):
        next_date = start_date + timedelta(days=20)
        url = (
            f"{etl_config.USGS_DATA_URL}/fdsnws/event/1/query?format=geojson"
            f"&starttime={start_date.strftime('%Y-%m-%d')}"
            f"&endtime={min(next_date, end_date).strftime('%Y-%m-%d')}"
        )
        USGSExtraction.init_extraction(
            metadata=USGSExtractionMetadata(
                url=url,
                type=USGSExtractionMetadataType.QUERY,
            ),
        )
        start_date = next_date
    logger.info("USGS historical data extraction completed")
