from datetime import datetime, timedelta

from celery import chain, shared_task

from apps.etl.extraction.sources.gfd.extract import GFDExtraction
from apps.etl.transform.sources.gfd import GFDTransformHandler


@shared_task
def ext_and_transform_gfd_historical_data():
    chain(
        GFDExtraction.task.s(),
        GFDTransformHandler.task.s(),
    ).apply_async()


@shared_task
def ext_and_transform_gfd_latest_data():
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=1)

    chain(
        GFDExtraction.task.s(start_date, end_date),
        GFDTransformHandler.task.s(),
    ).apply_async()
