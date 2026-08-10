from celery import shared_task

from apps.etl.extraction.sources.copernicus.extract import (
    CopernicusExtraction,
    CopernicusExtractionMetadata,
    CopernicusExtractionMetadataType,
    CopernicusExtractionParamsMetadata,
)
from main.celery import CeleryQueue
from main.configs import etl_config


@shared_task
def ext_and_transform_copernicus_latest_data():
    CopernicusExtraction.init_extraction(
        metadata=CopernicusExtractionMetadata(
            url=f"{etl_config.COPERNICUS_URL}/backend/dashboard-api/public-activations-info/",
            type=CopernicusExtractionMetadataType.QUERY,
            params=CopernicusExtractionParamsMetadata(
                limit=100,
                offset=0,
            ),
        ),
        queue_name=CeleryQueue.EXTRACTION,
    )
