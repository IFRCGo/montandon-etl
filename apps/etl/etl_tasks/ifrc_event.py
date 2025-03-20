from datetime import datetime

from celery import chain, shared_task
from django.conf import settings

from apps.etl.extraction.sources.ifrc_event.extract import IFRCEventExtraction, IFRCEventQueryVars
from apps.etl.models import ExtractionData
from apps.etl.transform.sources.ifrc_event import IFRCEventTransformHandler


@shared_task
def ext_and_transform_ifrcevent_latest_data():
    ext_object = (
        ExtractionData.objects.filter(
            source=ExtractionData.Source.DREF,
            status=ExtractionData.Status.SUCCESS,
            # FIXME: Why do we add filter that resp_data__isnull
            resp_data__isnull=False,
        )
        .order_by("-created_at")
        .first()
    )

    if ext_object:
        start_date = ext_object.created_at.date()
    else:
        start_date = datetime.strptime(settings.GLIDE_START_DATE, "%Y-%m-%d").date()

    url = f"{settings.IFRC_DATA_URL}/api/v2/event/?appeal_type=0,1"
    params: IFRCEventQueryVars = {
        "disaster_start_date__gte": start_date,
        "limit": 50,
        "offset": 0,
        "ordering": "-id",
        "format": "json",
    }
    chain(
        IFRCEventExtraction.task.s(url, params),
        IFRCEventTransformHandler.task.s(),
    ).apply_async()


@shared_task
def ext_and_transform_ifrcevent_historical_data():
    url = f"{settings.IFRC_DATA_URL}/api/v2/event/?appeal_type=0,1"
    params: IFRCEventQueryVars = {
        "disaster_start_date__gte": None,
        "limit": 50,
        "offset": 0,
        "ordering": "-id",
        "format": "json",
    }
    chain(
        IFRCEventExtraction.task.s(url, params),
        IFRCEventTransformHandler.task.s(),
    ).apply_async()
