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


@shared_task
def ext_and_transform_charter_data_for_activations(activation_ids: list[int]):
    for activation_id in activation_ids:
        activation_url = f"s3://{etl_config.CHARTER_S3_BUCKET_NAME}/activations/act-{activation_id}/act-{activation_id}.json"
        CharterExtraction.init_extraction(
            metadata=CharterExtractionMetadata(
                url=activation_url,
                type=CharterExtractionMetadataType.ACTIVATION,
                activation_id=activation_id,
            ),
            queue_name=CeleryQueue.EXTRACTION,
        )
