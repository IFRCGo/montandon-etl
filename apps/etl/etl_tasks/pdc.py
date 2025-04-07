from celery import shared_task
from datetime import datetime
from apps.etl.extraction.sources.pdc.extract import (
    PDCExtraction,
)
from main.configs import etl_config
from apps.etl.extraction.sources.pdc.extract import PdcHazardInputMetadata, Pagination, Restriction, HAZARD_TYPE_MAP

@shared_task
def extract_and_transform_pdc_data():
    data_url = f"{etl_config.PDC_SENTRY_BASE_URL}/hp_srv/services/hazards/t/json/get_active_hazards"
    PDCExtraction.task.s(data_url).apply_async()


@shared_task
def extract_and_transform_historical_pdc_data():
    pdc_start_date = str(etl_config.PDC_START_DATE)
    data =   datetime.strptime(pdc_start_date, "%Y-%m-%d")

# Convert datetime object to Unix timestamp (seconds since epoch)
    timestamp = str(int(data.timestamp()))
    print(timestamp)

    for event in HAZARD_TYPE_MAP:
        data = {
    "pagination": {
        "page": 1,
        "pagesize": 100
    },
    "restrictions": [
        [
            {
                "searchType": "GREATER_THAN",
                "createDate": timestamp
            },
            {
                "searchType": "EQUALS",
                "typeId": event
            }
        ]
    ]
        }
        # data = PdcHazardInputMetadata(
        #     pagination=Pagination(page=1, pagesize=100),
        #     restrictions=[
        #         [
        #             Restriction(searchType="GREATER_THAN", createDate=timestamp), # type: ignore
        #             Restriction(searchType="EQUALS", typeId=event) # type: ignore

        #         ]
        #     ]
        # ).model_dump()
        print(data)
        PDCExtraction.task.s(data).apply_async()


