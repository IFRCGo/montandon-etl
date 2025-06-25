from datetime import datetime

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
from main.configs import etl_config


@shared_task
def extract_and_transform_pdc_latest_data():
    data_url = f"{etl_config.PDC_SENTRY_BASE_URL}/hp_srv/services/hazards/t/json/search_hazard"
    pdc_latest_extraction = ExtractionData.objects.filter(
        source=ExtractionData.Source.PDC,
        status=ExtractionData.Status.SUCCESS,
    ).last()
    if pdc_latest_extraction:
        created_at = pdc_latest_extraction.created_at.strftime("%Y-%m-%d %H:%M:%S.%f")
        start_date = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S.%f")
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
        )


def extract_and_transform_historical_pdc_data():
    pdc_start_date = datetime.strptime(str(etl_config.PDC_START_DATE), "%Y-%m-%d")
    pdc_interval_years = etl_config.PDC_EXTRACTION_INTERVAL_YEARS

    pdc_end_date = pdc_start_date.replace(year=pdc_start_date.year + pdc_interval_years)
    if pdc_end_date > datetime.now():
        pdc_end_date = datetime.now()

    while pdc_start_date < pdc_end_date:
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
            )

        pdc_start_date = pdc_start_date.replace(year=pdc_start_date.year + pdc_interval_years)
        pdc_end_date = pdc_start_date.replace(year=pdc_start_date.year + pdc_interval_years)
        if pdc_end_date > datetime.now():
            pdc_end_date = datetime.now()
