from celery import shared_task

from apps.etl.extraction.sources.gfd.extract import GFDExtraction, GFDExtractionMetadata, GFDExtractionMetadataType
from main.celery import CeleryQueue


@shared_task
def ext_and_transform_gfd_historical_data():
    """Extract and Transform GFD historical data"""
    url = "https://earthengine.googleapis.com/v1alpha/projects/earthengine-legacy/assets/GLOBAL_FLOOD_DB/MODIS_EVENTS/V1"
    GFDExtraction.init_extraction(
        metadata=GFDExtractionMetadata(url=url, type=GFDExtractionMetadataType.QUERY), queue_name=CeleryQueue.EXTRACTION
    )
