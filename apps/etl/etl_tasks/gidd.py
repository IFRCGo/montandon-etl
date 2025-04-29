from celery import chain, shared_task

from apps.etl.extraction.sources.gidd.extract import GIDDExtraction, GIDDExtractionMetadata, GIDDExtractionMetadataType
from apps.etl.transform.sources.gidd import GIDDTransformHandler
from main.configs import etl_config


@shared_task
def ext_and_transform_gidd_latest_data():
    """Extract and Transform the GIDD data"""
    url = f"{etl_config.IDMC_DATA_URL}/external-api/gidd/disaggregations/disaggregation-geojson/"
    extraction_obj = GIDDExtraction.init_extraction(
        metadata=GIDDExtractionMetadata(url=url, type=GIDDExtractionMetadataType.QUERY)
    )
    chain(
        GIDDExtraction.task.s(extraction_obj.id),
        GIDDTransformHandler.task.s(),
    ).apply_async()
