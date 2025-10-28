from celery import shared_task

from apps.etl.extraction.sources.gidd.extract import GIDDExtraction, GIDDExtractionMetadata, GIDDExtractionMetadataType
from main.celery import CeleryQueue
from main.configs import etl_config


@shared_task
def ext_and_transform_gidd_latest_data():
    """Extract and Transform the GIDD data"""
    url = f"{etl_config.IDMC_DATA_URL}/external-api/gidd/disaggregations/disaggregation-geojson/"
    GIDDExtraction.init_extraction(
        metadata=GIDDExtractionMetadata(url=url, type=GIDDExtractionMetadataType.QUERY), queue_name=CeleryQueue.EXTRACTION
    )
