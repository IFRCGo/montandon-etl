import json
import logging

from celery import chain, shared_task
from django.conf import settings

from apps.etl.extraction.sources.usgs.extract import USGSExtraction
from apps.etl.models import ExtractionData
from apps.etl.transform.sources.usgs import USGSTransformHandler

logger = logging.getLogger(__name__)


def ext_and_transform_usgs_data(url: str):
    """Extract and Transform USGS data"""
    BATCH_SIZE = 50
    headers = {"Content-Type": "application/json"}

    # Handles base extraction from the all day url
    base_extraction_id = USGSExtraction.handle_extraction(
        url=url, params=None, headers=headers, source=ExtractionData.Source.USGS
    )

    if base_extraction_id:
        instance_id = ExtractionData.objects.get(id=base_extraction_id)
        response_data = json.loads(instance_id.resp_data.read())
        # FIXME: We might need to write a simple validator here
        features_list = response_data["features"]
        for i in range(0, len(features_list), BATCH_SIZE):
            feature_batch = features_list[i : i + BATCH_SIZE]
            for feature_item in feature_batch:
                if "detail" in feature_item["properties"]:
                    chain(
                        USGSExtraction.task.s(base_extraction_id, feature_item["properties"]["detail"]),
                        USGSTransformHandler.task.s(),
                    ).apply_async(countdown=30)
    else:
        logger.error("Base Extraction ID not found")


# FIXME: This does not work if one of the system is down for more than a day
@shared_task
def ext_and_transform_usgs_latest_data():
    """Extract and Transform USGS latest data"""
    url = f"{settings.USGS_DATA_URL}/all_day.geojson"
    ext_and_transform_usgs_data(url=url)


@shared_task
def ext_and_transform_usgs_historical_data():
    """Extract and Transform USGS historical data"""
    # FIXME: Can we only get data for a month?
    url = f"{settings.USGS_DATA_URL}/all_month.geojson"
    ext_and_transform_usgs_data(url=url)
