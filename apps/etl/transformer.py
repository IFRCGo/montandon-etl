from celery import shared_task
from celery.result import AsyncResult


@shared_task
def transform_1(data):
    print("Trandformation 1 started")
    print("Data :", data)
    print("Trandformation 1 ended")

@shared_task
def transform_2(transform_id : int):
    result = AsyncResult(transform_id)
    if result == "SUCCESS":
        print("Trandformation 2 started")
        print("Trandformation 2 ended")

@shared_task
def transform_3(transform_id : int):
    result = AsyncResult(transform_id)
    if result == "SUCCESS":
        print("Trandformation 2 started")
        print("Trandformation 2 ended")
