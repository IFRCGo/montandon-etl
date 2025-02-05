from celery import chain, shared_task
from datetime import datetime, timedelta

from apps.etl.extraction.sources.global_flood_database.extract import GFDExtraction
# from apps.etl.transform.sources.gidd import GFDTransformHandler


@shared_task
def ext_and_transform_gfd_data():
    GFDExtraction.task()


@shared_task
def ext_and_transform_gfd_latest_data():
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=1)

    GFDExtraction.task(start_date, end_date)
