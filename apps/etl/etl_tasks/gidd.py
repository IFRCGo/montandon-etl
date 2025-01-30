import logging

from celery import shared_task
from pystac_monty.sources.gidd import GIDDDataSource, GIDDTransformer

from apps.etl.extraction.sources.gidd.extract import GIDDExtraction
from apps.etl.transform.sources.gidd import GIDDTransformHandler

logger = logging.getLogger(__name__)

# HISTORICAL_DATA_URL = "https://helix-tools-api.idmcdb.org/external-api/gidds/gidds_all_retrieve"
LATEST_DATA_URL = "https://helix-tools-api.idmcdb.org/external-api/gidds/last-180-days/"
HISTORICAL_DATA_URL = "https://helix-tools-api.idmcdb.org/external-api/gidd/disaggregations/disaggregation-geojson/?client_id=IDMCWSHSOLO009"


@shared_task
def extract_and_transform_data(url):
    extraction = GIDDExtraction(url=url)
    extraction_data = extraction.process_data()

    schema = GIDDDataSource(source_url=url, data=extraction_data["data"])
    transformer = GIDDTransformHandler(
        extraction_id=extraction_data["extraction_id"], transformer_schema=schema, transformer=GIDDTransformer
    )
    transform_data = transformer.transform_data()

    transformer.load_stac_item_to_queue(transform_data)


@shared_task
def ext_and_transform_historical_data():
    extract_and_transform_data(HISTORICAL_DATA_URL)


@shared_task
def ext_and_transform_latest_data():
    extract_and_transform_data(LATEST_DATA_URL)

print("GIDD Transform")
ext_and_transform_historical_data()
print("GIDD Transform Ended")
