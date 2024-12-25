import logging
from celery import shared_task
from celery.result import AsyncResult

from pystac_monty.sources.gdacs import (
    GDACSTransformer,
    GDACSDataSourceType,
    GDACSDataSource,
)

from apps.etl.models import ExtractionData, GdacsTransformation

logger = logging.getLogger(__name__)


@shared_task
def transform_event_data(gdacs_instance_id):
    print("Trandformation started for event data")

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

    try:
        transformed_event_item = transformer.make_source_event_item()
        transformed_item_dict = transformed_event_item.to_dict()

        GdacsTransformation.objects.create(
            extraction=gdacs_instance,
            item_type=GdacsTransformation.ItemType.EVENT,
            data=transformed_item_dict,
            status=GdacsTransformation.TransformationStatus.SUCCESS,
            failed_reason="",
        )
    except Exception as e:
        logging.error(e)
        GdacsTransformation.objects.create(
            extraction=gdacs_instance,
            item_type=GdacsTransformation.ItemType.EVENT,
            status=GdacsTransformation.TransformationStatus.FAILED,
            failed_reason=e,
        )
    print("Trandformation ended for event data")


@shared_task
def transform_geo_data(gdacs_instance_id):
    print("Transformation started for hazard data")

    gdacs_instance = ExtractionData.objects.get(id=gdacs_instance_id)
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
    try:
        transformed_geo_item = transformer.make_hazard_event_item()
        transformed_item_dict = transformed_geo_item.to_dict()

        GdacsTransformation.objects.create(
            extraction=gdacs_instance,
            item_type=GdacsTransformation.ItemType.HAZARD,
            data=transformed_item_dict,
            status=GdacsTransformation.TransformationStatus.SUCCESS,
            failed_reason="",
        )
    except Exception as e:
        logging.error(e)
        GdacsTransformation.objects.create(
            extraction=gdacs_instance,
            item_type=GdacsTransformation.ItemType.HAZARD,
            status=GdacsTransformation.TransformationStatus.FAILED,
            failed_reason=e,
        )
    print("Transformation ended for hazard data")


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

    try:
        transformed_impact_item = transformer.make_impact_items()
        transformed_item_dict = {"data": transformed_impact_item}

        GdacsTransformation.objects.create(
            extraction=gdacs_instance,
            item_type=GdacsTransformation.ItemType.IMPACT,
            data=transformed_item_dict,
            status=GdacsTransformation.TransformationStatus.SUCCESS,
            failed_reason="",
        )
    except Exception as e:
        logging.error(e)
        GdacsTransformation.objects.create(
            extraction=gdacs_instance,
            item_type=GdacsTransformation.ItemType.IMPACT,
            status=GdacsTransformation.TransformationStatus.FAILED,
            failed_reason=e,
        )
    print("Transformation ended for impact data")

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
