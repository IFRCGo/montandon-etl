from celery import chain, shared_task

from apps.etl.extraction.sources.gidd.extract import GIDDExtraction
from apps.etl.transform.sources.gidd import GIDDTransformHandler


@shared_task
def ext_and_transform_gidd_latest_data():
    chain(
        GIDDExtraction.task.s(),
        GIDDTransformHandler.task.s(),
    ).apply_async()
