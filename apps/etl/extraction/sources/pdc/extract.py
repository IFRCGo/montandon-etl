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
from apps.etl.models import ExtractionData, HazardType

logger = logging.getLogger(__name__)

HAZARD_TYPE_MAP = {
    "AVALANCHE": HazardType.OTHER,
    "DROUGHT": HazardType.DROUGHT,
    "EARTHQUAKE": HazardType.EARTHQUAKE,
    "EXTREMETEMPERATURE": HazardType.EXTREME_TEMPERATURE,
    "FLOOD": HazardType.FLOOD,
    "HIGHSURF": HazardType.OTHER,
    "HIGHWIND": HazardType.WIND,
    "LANDSLIDE": HazardType.LANDSLIDE,
    "SEVEREWEATHER": HazardType.OTHER,
    "STORM": HazardType.STORM,
    "TORNADO": HazardType.TORNADO,
    "CYCLONE": HazardType.CYCLONE,
    "TSUNAMI": HazardType.TSUNAMI,
    "VOLCANO": HazardType.VOLCANO,
    "WILDFIRE": HazardType.WILDFIRE,
    "WINTERSTORM": HazardType.OTHER,
}


@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def get_hazard_details(self, hazard_detail, **kwargs):
    r = requests.get(
        f"{settings.PDC_BASE_URL}/hazard/{hazard_detail['uuid']}/exposure",
        headers={"Authorization": f"Bearer {settings.PDC_AUTHORIZATION_KEY}"},
    )
    exposure = {}
    for exposure_id in r.json():
        print(f"Progress: {exposure_id}")
        detail_url = f"{settings.PDC_BASE_URL}/hazard/{hazard_detail['uuid']}/exposure/{exposure_id}"
        detail_response = requests.get(
            url=detail_url,
            headers={"Authorization": f"Bearer {settings.PDC_AUTHORIZATION_KEY}"},
        )
        print(detail_response.text)
        if detail_response.status_code == 200:
            # exposure.update({exposure_id: detail_response.json()})
            exposure[exposure_id] = detail_response.json()
    return {**hazard_detail, "exposure": exposure}


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
            for hazard in response_data:
                if hazard["type_ID"] not in HAZARD_TYPE_MAP.keys():
                    continue
                hazard_detail = get_hazard_details(hazard_detail=hazard)
                store_pdc_exposure_data(
                    response=hazard_detail,
                    source=ExtractionData.Source.PDC,
                    validate_source_func=None,
                    parent_id=pdc_instance.id,
                    instance_id=pdc_instance.id,
                    hazard_type=HAZARD_TYPE_MAP[hazard["type_ID"]],
                )

            logger.info("PDC data imported sucessfully")
        return pdc_instance.id

    logger.info("PDC data import failed")
