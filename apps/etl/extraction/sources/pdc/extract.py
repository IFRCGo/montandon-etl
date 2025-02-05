import json
import logging

import requests
from celery import shared_task
from django.conf import settings

from apps.etl.extraction.sources.base.extract import Extraction
from apps.etl.extraction.sources.base.utils import (
    store_extraction_data,
    store_pdc_exposure_data,
)
from apps.etl.models import ExtractionData

logger = logging.getLogger(__name__)

HAZARD_TYPES = [
    "AVALANCHE",
    "DROUGHT",
    "EARTHQUAKE",
    "EXTREMETEMPERATURE",
    "FLOOD",
    "HIGHSURF",
    "HIGHWIND",
    "LANDSLIDE",
    "SEVEREWEATHER",
    "STORM",
    "TORNADO",
    "CYCLONE",
    "TSUNAMI",
    "VOLCANO",
    "WILDFIRE",
    "WINTERSTORM",
]



@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def get_exposure_data(self, hazard_list, **kwargs):
    timestamps = []
    exposure_data = {}
    for count, hazard in enumerate(hazard_list[190:220]):
        print(f'Progress: {count+1}/{len(hazard_list) } hazard uuid is {hazard["uuid"]}')
    # for hazard in hazard_list:
        # TODO we need to handle category id RESPONSE in future for now ignore this
        if hazard["type_ID"] not in HAZARD_TYPES:
            print("Skipping EXERCISE and RESPONSE category")
            continue
        exposure_url = f"{settings.PDC_BASE_URL}/hazard/{hazard['uuid']}/exposure"
        response = requests.get(
            url=exposure_url,
            headers={"Authorization": f"Bearer {settings.PDC_AUTHORIZATION_KEY}"},
        )
        if response.status_code == 200:
            for count, exposure_id in enumerate(response.json()):
            # for exposure_id in response.json():
                print(
                    f'Progress: {count+1}/{len(response.json())} exposure id is {exposure_id} hazard uuid is {hazard["uuid"]}  hazard event is {hazard["type_ID"]}'
                )
                detail_url = f"{settings.PDC_BASE_URL}/hazard/{hazard['uuid']}/exposure/{exposure_id}"
                detail_response = requests.get(
                    url=detail_url,
                    headers={"Authorization": f"Bearer {settings.PDC_AUTHORIZATION_KEY}"},
                )
                timestamps.append({exposure_id: detail_response.json()})
                exposure_data[hazard["uuid"]] = timestamps
    return exposure_data


@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def import_hazard_data(self, **kwargs):
    """
    Import hazard data from pdc api
    """
    logger.info("Importing PDC data")
    pdc_url = f"{settings.PDC_BASE_URL}/hazards/t/json/get_active_hazards"

    # Create a Extraction object in the beginning
    instance_id = kwargs.get("instance_id", None)
    retry_count = kwargs.get("retry_count", None)

    pdc_instance = (
        ExtractionData.objects.get(id=instance_id)
        if instance_id
        else ExtractionData.objects.create(
            source=ExtractionData.Source.PDC,
            status=ExtractionData.Status.PENDING,
            source_validation_status=ExtractionData.ValidationStatus.NO_VALIDATION,
            hazard_type="",
            attempt_no=0,
            resp_code=0,
        )
    )

    # Extract the data from api.
    pdc_extraction = Extraction(
        url=pdc_url,
        headers={"Authorization": "Bearer {}".format(settings.PDC_AUTHORIZATION_KEY)},
    )
    response = None
    try:
        response = pdc_extraction.pull_data(
            source=ExtractionData.Source.PDC,
            ext_object_id=pdc_instance.id,
            retry_count=retry_count if retry_count else 1,
        )
    except requests.exceptions.RequestException as exc:
        self.retry(exc=exc, kwargs={"instance_id": pdc_instance.id, "retry_count": self.request.retries})

    if response:
        # Save the extracted data into the existing pdc object
        pdc_instance = store_extraction_data(
            response=response,
            source=ExtractionData.Source.PDC,
            validate_source_func=None,
            instance_id=pdc_instance.id,
        )
        if pdc_instance.resp_code == 200:
            response_data = json.loads(pdc_instance.resp_data.read())
            data = get_exposure_data(response_data)
            store_pdc_exposure_data(
                response=data,
                source=ExtractionData.Source.PDC,
                validate_source_func=None,
                parent_id=pdc_instance.id,
                instance_id=pdc_instance.id,
            )
            logger.info("PDC data imported sucessfully")
        return pdc_instance.id
