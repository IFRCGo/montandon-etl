from celery import chain, shared_task

from apps.etl.extraction.sources.gfd.extract import GFDExtraction
from apps.etl.transform.sources.gfd import GFDTransformHandler


@shared_task
def ext_and_transform_gfd_historical_data():
    chain(
        GFDExtraction.task.s(),
        GFDTransformHandler.task.s(),
    ).apply_async()
