from celery import shared_task
from celery.result import AsyncResult

from pystac_monty.sources.gdacs import (
    GDACSTransformer,
    GDACSDataSourceType,
    GDACSDataSource,
)

from apps.etl.models import ExtractionData


@shared_task
def transform_event_data(gdacs_instance_id):
    print("Trandformation started for hazard data")
    print("Instance id", gdacs_instance_id)

    gdacs_instance = ExtractionData.objects.get(id=gdacs_instance_id)

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

    return transformed_event_item.to_dict()


@shared_task
def transform_geo_data(gdacs_instance_id):
    print("Transformation started for hazard data")

    gdacs_instance = ExtractionData.objects.get(id=gdacs_instance_id)
    print("GDACS GEo ID", gdacs_instance.id)
    data_file_path = gdacs_instance.resp_data.path  # Absolute file path
    with open(data_file_path, 'r') as file:
        data = file.read()
    transformer = GDACSTransformer(
        [
            GDACSDataSource(
                type=GDACSDataSourceType.GEOMETRY,
                source_url=gdacs_instance.url,
                data=data
            )
        ]
    )
    transformed_geo_item = transformer.make_hazard_event_item()

    return transformed_geo_item.to_dict()


@shared_task
def transform_impact_data(gdacs_instance_id):
    print("Transformation started for impact data")

    gdacs_instance = ExtractionData.objects.get(id=gdacs_instance_id)
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
    transformed_impact_item = transformer.make_impact_items()

    return transformed_impact_item


# @shared_task
# def transform_geometry_data(transform_id: int):
#     result = AsyncResult(transform_id)
#     if result.status == "SUCCESS":
#         print("Strarting transformation for geometry data")


# @shared_task
# def transform_population_exposure(transform_id: int):
#     result = AsyncResult(transform_id)
#     if result.status == "SUCCESS":
#         print("Strarting transformation for population exposure")
