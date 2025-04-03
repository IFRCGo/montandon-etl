import json
import logging
from datetime import datetime, timedelta

from celery import chain, shared_task

from apps.etl.extraction.sources.usgs.extract import USGSExtraction
from apps.etl.models import ExtractionData
from apps.etl.transform.sources.usgs import USGSTransformHandler
from main.configs import etl_config
from main.logging import log_extra

logger = logging.getLogger(__name__)


def ext_and_transform_usgs_data(url: str):
    """Extract and Transform USGS data"""

    # Handles base extraction from the all day url
    base_extraction_id = USGSExtraction.handle_extraction(
        url=url, params=None, headers={"Content-Type": "application/json"}, source=ExtractionData.Source.USGS
    )

    if base_extraction_id:
        instance_id = ExtractionData.objects.get(id=base_extraction_id)
        response_data = json.loads(instance_id.resp_data.read())
        # FIXME: We might need to write a simple validator here
        features_list = response_data["features"]

        BATCH_SIZE = 50
        for i in range(0, len(features_list), BATCH_SIZE):
            feature_batch = features_list[i : i + BATCH_SIZE]
            for feature_item in feature_batch:
                if "detail" in feature_item["properties"]:
                    detail_url = feature_item["properties"]["detail"]
                    chain(
                        USGSExtraction.task.s(detail_url, base_extraction_id),
                        USGSTransformHandler.task.s(),
                    ).apply_async(countdown=30)
    else:
        logger.error(
            "Base Extraction ID not found",
            exc_info=True,
            extra=log_extra({"extraction_id": base_extraction_id}),
        )


# FIXME: This does not work if one of the system is down for more than a day
@shared_task
def ext_and_transform_usgs_latest_data():
    """Extract and Transform USGS latest data"""
    url = f"{etl_config.USGS_DATA_URL}/earthquakes/feed/v1.0/summary/all_day.geojson"
    ext_and_transform_usgs_data(url=url)


@shared_task
def ext_and_transform_usgs_historical_data():
    """Extract and Transform USGS historical data"""
    start_date = etl_config.USGS_START_DATE
    end_date = datetime.now().date()

    while start_date.strftime("%Y-%m-%d") < end_date.strftime("%Y-%m-%d"):
        next_date = start_date + timedelta(days=30 * 7)  # Approx. 7 months
        url = (
            f"{etl_config.USGS_DATA_URL}/fdsnws/event/1/query?format=geojson"
            f"&starttime={start_date.strftime('%Y-%m-%d')}"
            f"&endtime={min(next_date, end_date).strftime('%Y-%m-%d')}"
        )
        ext_and_transform_usgs_data(url=url)
        start_date = next_date
