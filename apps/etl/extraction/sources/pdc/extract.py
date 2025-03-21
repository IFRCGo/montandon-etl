import json
import logging
import uuid

import requests
from django.conf import settings
from django.core.files.base import ContentFile

from apps.etl.extraction.sources.base.handler import BaseExtraction
from apps.etl.models import ExtractionData, HazardType
from apps.etl.transform.sources.pdc import PDCTransformHandler
from apps.etl.utils import AccessTokenManager
from main.celery import app

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


class PDCExtraction(BaseExtraction):
    @staticmethod
    def fetch_geo_json(hazard_uuid):
        geo = AccessTokenManager(requests.Session())
        return geo.get_polygon(hazard_uuid)

    @staticmethod
    def fetch_exposure_data(hazard_uuid):
        url = f"{settings.PDC_BASE_URL}/hazard/{hazard_uuid}/exposure"
        headers = {"Authorization": f"Bearer {settings.PDC_AUTHORIZATION_KEY}"}
        return requests.get(url, headers=headers).json()

    @staticmethod
    def fetch_exposure_detail(hazard_uuid: uuid, exposure_id: int):
        url = f"{settings.PDC_BASE_URL}/hazard/{hazard_uuid}/exposure/{exposure_id}"
        headers = {"Authorization": f"Bearer {settings.PDC_AUTHORIZATION_KEY}"}
        return requests.get(url, headers=headers).json()

    @classmethod
    def store_pdc_exposure_data(
        cls,
        response,
        source=None,
        validate_source_func=None,
        instance_id=None,
        parent_id=None,
        hazard_type=None,
        metadata=None,
    ):
        file_extension = "json"
        file_name = f"{instance_id}pdc.{file_extension}"
        data = json.dumps(response).encode("utf-8")
        instance = cls._create_extraction_instance(
            url="",
            source=source,
            parent_id=parent_id.id,
            status=ExtractionData.Status.SUCCESS,
            hazard_type=hazard_type,
            metadata=metadata,
        )

        content_file = ContentFile(data)
        content_file.name = file_name
        instance.resp_data.save(content_file.name, content_file)

        return instance

    @classmethod
    def process_hazard(cls, instance, hazard):
        if hazard["type_ID"] not in HAZARD_TYPE_MAP:
            return
        try:
            geo_json_file = cls.fetch_geo_json(hazard["uuid"])
            geo_json_data = cls.store_pdc_exposure_data(
                response=geo_json_file,
                source=ExtractionData.Source.PDC,
                validate_source_func=None,
                parent_id=instance,
                hazard_type=HAZARD_TYPE_MAP.get(hazard["type_ID"]),
                metadata={},
            )

            exposure_ids = cls.fetch_exposure_data(hazard["uuid"])
            for exposure_id in exposure_ids:
                if ExtractionData.objects.filter(
                    metadata__exposure_id=exposure_id,
                    source=ExtractionData.Source.PDC,
                    status=ExtractionData.Status.SUCCESS,
                    metadata__uuid=hazard["uuid"],
                ).exists():
                    continue

                details = cls.fetch_exposure_detail(hazard["uuid"], exposure_id)
                exposure_detail = cls.store_pdc_exposure_data(
                    response=details,
                    source=ExtractionData.Source.PDC,
                    validate_source_func=None,
                    parent_id=instance,
                    hazard_type=HAZARD_TYPE_MAP.get(hazard["type_ID"]),
                    metadata={"exposure_id": exposure_id, "uuid": hazard["uuid"]},
                )
                PDCTransformHandler.task(exposure_detail.id, geo_json_data.id)
        except Exception as exc:
            raise exc

    @classmethod
    def handle_extraction(cls, url: str, params: dict, headers: dict, source: int, parent_id=None) -> dict:
        """
        Process data extraction.
        Returns:
            int: ID of the extraction instance
        """
        logger.info("Starting data extraction")
        instance = cls._create_extraction_instance(url=url, source=source, parent_id=parent_id)

        try:
            cls._update_instance_status(instance, ExtractionData.Status.IN_PROGRESS)

            response = requests.get(url, params=params, headers=headers, timeout=30)
            response.raise_for_status()
            instance.resp_code = response.status_code
            instance.save(update_fields=["resp_code"])

            if response.status_code == 200:
                response_data = cls._save_response_data(instance, response)
                # Check if response contains data
                if response_data:
                    cls._update_instance_status(instance, ExtractionData.Status.SUCCESS)
                    logger.info("Data extracted successfully")
                    for hazard in response_data:
                        cls.process_hazard(instance, hazard)
                else:
                    cls._update_instance_status(
                        instance,
                        ExtractionData.Status.SUCCESS,
                        ExtractionData.ValidationStatus.NO_DATA,
                        update_validation=True,
                    )
                    logger.warning("No hazard data found in response")

            return instance.id

        except requests.exceptions.RequestException:
            cls._update_instance_status(instance, ExtractionData.Status.FAILED)
            logger.error(
                "extraction failed",
                exc_info=True,
                extra={
                    "source": instance.source,
                },
            )
            raise

    @staticmethod
    @app.task
    def task(data_url, header):
        return PDCExtraction.handle_extraction(url=data_url, params=None, headers=header, source=ExtractionData.Source.PDC)
