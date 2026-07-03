from celery import shared_task

from apps.etl.extraction.sources.disaster_charter.extract import (
    CharterExtraction,
    CharterExtractionMetadata,
    CharterExtractionMetadataType,
)
from main.celery import CeleryQueue
from main.configs import etl_config


@shared_task
def ext_and_transform_charter_latest_data():
    catalog_url = f"s3://{etl_config.CHARTER_S3_BUCKET_NAME}/activations/"
    CharterExtraction.init_extraction(
        metadata=CharterExtractionMetadata(
            url=catalog_url,
            type=CharterExtractionMetadataType.CATALOG,
        ),
        queue_name=CeleryQueue.EXTRACTION,
    )
