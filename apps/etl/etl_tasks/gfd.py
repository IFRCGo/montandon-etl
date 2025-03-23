from datetime import date, datetime

from celery import chain, shared_task

from apps.etl.extraction.sources.gfd.extract import GFDExtraction
from apps.etl.models import ExtractionData
from apps.etl.transform.sources.gfd import GFDTransformHandler
from main.configs import etl_config


@shared_task
def ext_and_transform_gfd_historical_data():
    chain(
        GFDExtraction.task.s(),
        GFDTransformHandler.task.s(),
    ).apply_async()


@shared_task
def ext_and_transform_gfd_latest_data():
    ext_object = (
        ExtractionData.objects.filter(
            source=ExtractionData.Source.GFD, status=ExtractionData.Status.SUCCESS, resp_data__isnull=False
        )
        .order_by("-created_at")
        .first()
    )

    if ext_object:
        start_date: date = ext_object.created_at.date()
    else:
        start_date = etl_config.GFD_START_DATE
    end_date = datetime.now().date()

    chain(
        GFDExtraction.task.s(start_date, end_date),
        GFDTransformHandler.task.s(),
    ).apply_async()
