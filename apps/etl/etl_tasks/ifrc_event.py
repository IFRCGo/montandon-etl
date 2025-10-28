import datetime
from datetime import date
from urllib.parse import urlencode

from celery import shared_task

from apps.etl.extraction.sources.ifrc_event.extract import (
    IfrcEventExtractionInputMetadata,
    IFRCEventExtractionV2,
    IFRCExtractionMetadata,
    IFRCExtractionMetadataType,
)
from apps.etl.models import ExtractionData
from main.celery import CeleryQueue
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
        start_date = etl_config.IFRC_EVENT_START_DATE

    params = IfrcEventExtractionInputMetadata(
        disaster_start_date__gte=str(start_date),
        disaster_start_date__lte=str(datetime.datetime.today().date()),
        limit=50,
        offset=0,
        ordering="-id",
        format="json",
    )
    params_dict = {k: v for k, v in params.model_dump().items() if v is not None}
    # Encode parameters into URL query string
    query_string = urlencode(params_dict)
    url = f"{etl_config.IFRC_DATA_URL}/api/v2/event/?appeal_type=0,1&{query_string}"
    IFRCEventExtractionV2.init_extraction(
        metadata=IFRCExtractionMetadata(url=url, type=IFRCExtractionMetadataType.QUERY), queue_name=CeleryQueue.EXTRACTION
    )


@shared_task
def ext_and_transform_ifrcevent_historical_data(
    start_date: date,
    end_date: date,
):
    params = IfrcEventExtractionInputMetadata(
        disaster_start_date__gte=str(start_date),
        disaster_start_date__lte=str(end_date),
        limit=500,
        offset=0,
        ordering="-id",
        format="json",
    )
    # Convert params to dict and filter out None values
    params_dict = {k: v for k, v in params.model_dump().items() if v is not None}
    # Encode parameters into URL query string
    query_string = urlencode(params_dict)
    url = f"{etl_config.IFRC_DATA_URL}/api/v2/event/?appeal_type=0,1&{query_string}"
    IFRCEventExtractionV2.init_extraction(
        metadata=IFRCExtractionMetadata(url=url, type=IFRCExtractionMetadataType.QUERY), queue_name=CeleryQueue.EXTRACTION
    )
