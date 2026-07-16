from datetime import date, datetime

from celery import shared_task

from apps.etl.extraction.sources.pdc.extract import (
    HAZARD_TYPE_MAP,
    Pagination,
    PDCExtractionMetadata,
    PDCExtractionMetaDataType,
    PDCExtractionV2,
    PdcHazardInputMetadata,
    Restriction,
)
from apps.etl.models import ExtractionData
from main.celery import CeleryQueue
from main.configs import etl_config


@shared_task
def extract_and_transform_pdc_latest_data():
    data_url = f"{etl_config.PDC_SENTRY_BASE_URL}/hp_srv/services/hazards/t/json/search_hazard"
    pdc_latest_extraction = (
        ExtractionData.objects.filter(
            source=ExtractionData.Source.PDC,
            status=ExtractionData.Status.SUCCESS,
            metadata__type=PDCExtractionMetaDataType.HAZARD,
            metadata__hazard__pagination__page=1,
        )
        .order_by("-created_at")
        .first()
    )

    if pdc_latest_extraction:
        # The row's created_at drifts from the actual query window (pagination/queue delays),
        # so read the window's own LESS_THAN bound instead of the row's insert time.
        less_than = next(
            restriction["createDate"]
            for group in pdc_latest_extraction.metadata["hazard"]["restrictions"]
            for restriction in group
            if restriction["searchType"] == "LESS_THAN"
        )
        start_date = datetime.fromtimestamp(int(less_than) / 1000)
    else:
        start_date = datetime.strptime(str(etl_config.PDC_START_DATE), "%Y-%m-%d")

    end_date = datetime.now()

    for event in HAZARD_TYPE_MAP.keys():
        data = PdcHazardInputMetadata(
            pagination=Pagination(page=1, pagesize=100),
            restrictions=[
                [
                    Restriction(searchType="GREATER_THAN", createDate=str(int(start_date.timestamp() * 1000))),  # type: ignore
                    Restriction(searchType="EQUALS", typeId=event),  # type: ignore
                    Restriction(searchType="LESS_THAN", createDate=str(int(end_date.timestamp() * 1000))),  # type: ignore
                ]
            ],
        )
        PDCExtractionV2.init_extraction(
            metadata=PDCExtractionMetadata(
                hazard=data,
                url=data_url,
                type=PDCExtractionMetaDataType.HAZARD,
            ),
            queue_name=CeleryQueue.EXTRACTION,
        )


def extract_and_transform_historical_pdc_data(
    start_date: date,
    end_date: date,
):
    pdc_start_date = datetime.strptime(str(start_date), "%Y-%m-%d")
    pdc_end_date = datetime.strptime(str(end_date), "%Y-%m-%d")

    url = f"{etl_config.PDC_SENTRY_BASE_URL}/hp_srv/services/hazards/t/json/search_hazard"
    for event in HAZARD_TYPE_MAP.keys():
        data = PdcHazardInputMetadata(
            pagination=Pagination(page=1, pagesize=100),
            restrictions=[
                [
                    Restriction(searchType="GREATER_THAN", createDate=str(int(pdc_start_date.timestamp() * 1000))),  # type: ignore
                    Restriction(searchType="EQUALS", typeId=event),  # type: ignore
                    Restriction(searchType="LESS_THAN", createDate=str(int(pdc_end_date.timestamp() * 1000))),
                ]
            ],
        )
        PDCExtractionV2.init_extraction(
            metadata=PDCExtractionMetadata(
                hazard=data,
                url=url,
                type=PDCExtractionMetaDataType.HAZARD,
            ),
            queue_name=CeleryQueue.EXTRACTION,
        )
