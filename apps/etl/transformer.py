from celery import shared_task
from celery.result import AsyncResult


@shared_task
def transform_1(data):
    print("Trandformation 1 started")
    print("Data :", data)
    print("Trandformation 1 ended")


@shared_task
def transform_2(transform_id: int):
    print("Transformation 2 started")
    result = AsyncResult(transform_id)
    if result.status == "SUCCESS":
        print("Trandformation 1 Success")
        print("Strarting transformation 2")


@shared_task
def transform_3(transform_id: int):
    result = AsyncResult(transform_id)
    if result.status == "SUCCESS":
        print("Trandformation 1 Success")
        print("Strarting transformation 3")
