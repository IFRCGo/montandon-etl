from celery import shared_task
from celery.result import AsyncResult

from pystac_monty.sources.gdacs import (
    GDACSTransformer,
    GDACSDataSourceType,
    GDACSDataSource,
)

@shared_task
def transform_event_data(gdacs_instance):
    print("Trandformation started for hazard data")

    data_file_path = gdacs_instance.resp_data.path  # Absolute file path
    with open(data_file_path, 'r') as file:
        data = file.read()
    transformer = GDACSTransformer(
        [
            GDACSDataSource(
                type=GDACSDataSourceType.EVENT,
                source_url=gdacs_instance.url,
                data=data
            )
        ]
    )
    transformed_event_item = transformer.make_source_event_item()

    print("Trandformation for hazard data ended")
    return transformed_event_item



@shared_task
def transform_geometry_data(transform_id: int):
    result = AsyncResult(transform_id)
    if result.status == "SUCCESS":
        print("Strarting transformation for geometry data")


@shared_task
def transform_population_exposure(transform_id: int):
    result = AsyncResult(transform_id)
    if result.status == "SUCCESS":
        print("Strarting transformation for population exposure")
