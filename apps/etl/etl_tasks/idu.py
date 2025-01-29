import logging

from celery import shared_task
from pystac_monty.sources.idu import IDUDataSource, IDUTransformer

from apps.etl.extraction.sources.idu.extract import IDUExtraction
from apps.etl.transform.sources.idu import IDUTransformHandler

logger = logging.getLogger(__name__)

HISTORICAL_DATA_URL = "https://helix-tools-api.idmcdb.org/external-api/idus/idus_all_retrieve"
LATEST_DATA_URL = "https://helix-tools-api.idmcdb.org/external-api/idus/last-180-days/"


@shared_task
def extract_and_transform_data(url):
    try:
        extraction = IDUExtraction(url=url)
        extraction_data = extraction.process_data()

        schema = IDUDataSource(source_url=url, data=extraction_data["data"])
        transformer = IDUTransformHandler(
            extraction_id=extraction_data["extraction_id"], transformer_schema=schema, transformer=IDUTransformer
        )
        transform_data = transformer.transform_data()

        transformer.load_stac_item_to_queue(transform_data)
    except Exception as e:
        logger.error("Fail to extract or transform IDU data", exc_info=True)
        raise e


@shared_task
def ext_and_transform_historical_data():
    extract_and_transform_data(HISTORICAL_DATA_URL)


@shared_task
def ext_and_transform_latest_data():
    extract_and_transform_data(LATEST_DATA_URL)
