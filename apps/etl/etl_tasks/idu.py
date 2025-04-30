import logging

from celery import chain, shared_task

from apps.etl.extraction.sources.idu.extract import IDUExtraction, IDUExtractionMetadata, IDUExtractionMetadataType
from apps.etl.transform.sources.idu import IDUTransformHandler
from main.configs import etl_config

logger = logging.getLogger(__name__)


@shared_task
def ext_and_transform_idu_historical_data():
    """Extract and Transform IDU historical data"""
    url = f"{etl_config.IDMC_DATA_URL}/external-api/idus/all/"
    extraction_obj = IDUExtraction.init_extraction(
        metadata=IDUExtractionMetadata(url=url, type=IDUExtractionMetadataType.QUERY), add_to_queue=False
    )
    chain(IDUExtraction.task.s(extraction_obj.id), IDUTransformHandler.task.s()).apply_async()


@shared_task
def ext_and_transform_idu_latest_data():
    """Extract and Transform IDU latest data"""
    url = f"{etl_config.IDMC_DATA_URL}/external-api/idus/last-180-days/"

    extraction_obj = IDUExtraction.init_extraction(
        metadata=IDUExtractionMetadata(url=url, type=IDUExtractionMetadataType.QUERY), add_to_queue=False
    )
    chain(IDUExtraction.task.s(extraction_obj.id), IDUTransformHandler.task.s()).apply_async()
