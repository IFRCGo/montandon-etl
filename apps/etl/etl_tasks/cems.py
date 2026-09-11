from celery import shared_task

from apps.etl.extraction.sources.cems.extract import (
    CEMSExtraction,
    CEMSExtractionMetadata,
    CEMSExtractionMetadataType,
    CEMSExtractionParamsMetadata,
)
from main.celery import CeleryQueue
from main.configs import etl_config


@shared_task
def ext_and_transform_cems_latest_data():
    CEMSExtraction.init_extraction(
        metadata=CEMSExtractionMetadata(
            url=f"{etl_config.CEMS_URL}/backend/dashboard-api/public-activations-info/",
            type=CEMSExtractionMetadataType.QUERY,
            params=CEMSExtractionParamsMetadata(
                limit=100,
                offset=0,
            ),
        ),
        queue_name=CeleryQueue.EXTRACTION,
    )
