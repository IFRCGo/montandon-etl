from datetime import datetime, timedelta

from celery import chain, shared_task

from apps.etl.extraction.sources.gfd.extract import GFDExtraction
from apps.etl.models import ExtractionData
from apps.etl.transform.sources.gfd import GFDTransformHandler


@shared_task
def ext_and_transform_gfd_historical_data():
    chain(
        GFDExtraction.task.s(),
        GFDTransformHandler.task.s(),
    ).apply_async()


# TODO Remove if not required.
@shared_task
def ext_and_transform_gfd_latest_data():
    ext_object = (
        ExtractionData.objects.filter(
            source=ExtractionData.Source.GFD, status=ExtractionData.Status.SUCCESS, resp_data__isnull=False
        )
        .order_by("-created_at")
        .first()
    )

    end_date = datetime.now().date()

    if ext_object:
        start_date = ext_object.created_at.date()
    else:
        start_date = end_date - timedelta(days=7)

    chain(
        GFDExtraction.task.s(start_date, end_date),
        GFDTransformHandler.task.s(),
    ).apply_async()
