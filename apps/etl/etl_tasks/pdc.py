from datetime import datetime

from celery import shared_task

from apps.etl.extraction.sources.pdc.extract import (
    HAZARD_TYPE_MAP,
    Pagination,
    PDCExtraction,
    PdcHazardInputMetadata,
    Restriction,
)
from main.configs import etl_config


@shared_task
def ext_and_transform_pdc_latest_data():
    # TODO Fix according to latest extraction logic that accepts Metadata
    data_url = f"{etl_config.PDC_SENTRY_BASE_URL}/hp_srv/services/hazards/t/json/get_active_hazards"
    PDCExtraction.task.s(data_url).apply_async()


@shared_task(queue="extraction")
def ext_and_transform_pdc_historical_data():
    pdc_start_date = datetime.strptime(str(etl_config.PDC_START_DATE), "%Y-%m-%d")
    pdc_interval_years = etl_config.PDC_EXTRACTION_INTERVAL_YEARS

    pdc_end_date = pdc_start_date.replace(year=pdc_start_date.year + pdc_interval_years)
    if pdc_end_date > datetime.now():
        pdc_end_date = datetime.now()

    while pdc_start_date < pdc_end_date:
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
            ).model_dump()
            PDCExtraction.task.s(data).apply_async(queue="extraction")
        pdc_start_date = pdc_start_date.replace(year=pdc_start_date.year + pdc_interval_years)
        pdc_end_date = pdc_start_date.replace(year=pdc_start_date.year + pdc_interval_years)
        if pdc_end_date > datetime.now():
            pdc_end_date = datetime.now()
