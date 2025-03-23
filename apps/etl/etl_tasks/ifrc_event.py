from celery import chain, shared_task

from apps.etl.extraction.sources.ifrc_event.extract import IFRCEventExtraction, IfrcEventExtractionInputMetadata
from apps.etl.models import ExtractionData
from apps.etl.transform.sources.ifrc_event import IFRCEventTransformHandler
from main.configs import etl_config


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
        start_date = etl_config.GLIDE_START_DATE

    params = IfrcEventExtractionInputMetadata(
        disaster_start_date__gte=start_date,
        limit=50,
        offset=0,
        ordering="-id",
        format="json",
    ).model_dump()
    chain(
        IFRCEventExtraction.task.s(params),
        IFRCEventTransformHandler.task.s(),
    ).apply_async()


@shared_task
def ext_and_transform_ifrcevent_historical_data():
    params = IfrcEventExtractionInputMetadata(
        disaster_start_date__gte=None,
        limit=50,
        offset=0,
        ordering="-id",
        format="json",
    )
    chain(
        IFRCEventExtraction.task.s(params),
        IFRCEventTransformHandler.task.s(),
    ).apply_async()
