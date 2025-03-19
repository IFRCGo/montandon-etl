import json
import logging
import uuid

import requests
from celery import shared_task
from django.conf import settings

from apps.etl.extraction.sources.base.extract import Extraction
from apps.etl.extraction.sources.base.utils import (
    store_extraction_data,
    store_pdc_exposure_data,
)
from apps.etl.models import ExtractionData, HazardType
from apps.etl.transform.sources.pdc import PDCTransformHandler
from apps.etl.utils import AccessTokenManager

logger = logging.getLogger(__name__)

HAZARD_TYPE_MAP = {
    "AVALANCHE": HazardType.OTHER,
    "DROUGHT": HazardType.DROUGHT,
    "EARTHQUAKE": HazardType.EARTHQUAKE,
    "EXTREMETEMPERATURE": HazardType.EXTREME_TEMPERATURE,
    "FLOOD": HazardType.FLOOD,
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
def get_hazard_details(self, extraction_id, **kwargs):
    instance_id = ExtractionData.objects.get(id=extraction_id)
    response_data = json.loads(instance_id.resp_data.read())
    geo = AccessTokenManager(requests.Session())
    for hazard in response_data:
        try:
            geo_json_file = geo.get_polygon(hazard["uuid"])

            geo_json_data = store_pdc_exposure_data(
                response=geo_json_file,
                source=ExtractionData.Source.PDC,
                validate_source_func=None,
                parent_id=instance_id,
                hazard_type=HAZARD_TYPE_MAP.get(hazard["type_ID"]),
                metadata={},
            )

            if hazard["type_ID"] not in HAZARD_TYPE_MAP.keys():
                continue
            r = requests.get(
                f"{settings.PDC_BASE_URL}/hazard/{hazard['uuid']}/exposure",
                headers={"Authorization": f"Bearer {settings.PDC_AUTHORIZATION_KEY}"},
            )
            for exposure_id in r.json():
                if ExtractionData.objects.filter(
                    metadata__exposure_id=exposure_id,
                    source=ExtractionData.Source.PDC,
                    status=ExtractionData.Status.SUCCESS,
                    metadata__uuid=hazard["uuid"],
                ).exists():
                    continue
                detail_url = f"{settings.PDC_BASE_URL}/hazard/{hazard['uuid']}/exposure/{exposure_id}"
                detail_response = requests.get(
                    url=detail_url,
                    headers={"Authorization": f"Bearer {settings.PDC_AUTHORIZATION_KEY}"},
                )
                exposure_detail = store_pdc_exposure_data(
                    response=detail_response.json(),
                    source=ExtractionData.Source.PDC,
                    validate_source_func=None,
                    parent_id=instance_id,
                    hazard_type=HAZARD_TYPE_MAP.get(hazard["type_ID"]),
                    metadata={"exposure_id": exposure_id, "uuid": hazard["uuid"]},
                )
                PDCTransformHandler.task(exposure_detail.id, geo_json_data.id)
        except Exception as exc:
            self.retry(exc=exc, kwargs={"instance_id": instance_id.id, "retry_count": self.request.retries})


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
            trace_id=str(uuid.uuid4()),
        )
    )

    # Extract the data from api.
    pdc_extraction = Extraction(
        url=pdc_url,
        headers={"Authorization": "Bearer {}".format(settings.PDC_AUTHORIZATION_KEY)},  # NOTE: Does this key expire??
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
        return pdc_instance.id

    logger.info("PDC data import failed")
