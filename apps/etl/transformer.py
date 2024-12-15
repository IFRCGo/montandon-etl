from celery import shared_task
from celery.result import AsyncResult


@shared_task
def transform_hazard_data(resp_data):
    print("Trandformation started for hazard data")
    print("Trandformation for hazard data ended")


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
