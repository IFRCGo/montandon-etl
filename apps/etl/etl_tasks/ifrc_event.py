from datetime import datetime, timedelta

from celery import chain, shared_task
from django.conf import settings

from apps.etl.extraction.sources.ifrc_event.extract import IFRCEventExtraction
from apps.etl.transform.sources.ifrc_event import IFRCEventTransformHandler

END_DATE = datetime.now().date()
START_DATE = END_DATE - timedelta(days=1)
HISTORICAL_DATA_PARAMS = {"limit": 50, "offset": 0, "ordering": "-id", "format": "json"}
LATEST_DATA_PARAMS = {"disaster_start_date__gte": START_DATE, "limit": 50, "offset": 0, "ordering": "-id", "format": "json"}
DATA_URL = f"{settings.IFRC_DATA_URL}/api/v2/event/?appeal_type=0,1"


@shared_task
def ext_and_transform_ifrcevent_latest_data():
    chain(
        IFRCEventExtraction.task.s(DATA_URL, LATEST_DATA_PARAMS),
        IFRCEventTransformHandler.task.s(),
    ).apply_async()


@shared_task
def ext_and_transform_ifrcevent_historical_data():
    chain(
        IFRCEventExtraction.task.s(DATA_URL, HISTORICAL_DATA_PARAMS),
        IFRCEventTransformHandler.task.s(),
    ).apply_async()
