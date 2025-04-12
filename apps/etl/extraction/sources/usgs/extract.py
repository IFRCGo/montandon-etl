import json
import logging

import requests

from apps.etl.extraction.sources.base.handler import BaseExtraction
from apps.etl.models import ExtractionData
from main.celery import CeleryQueue, app
from main.logging import log_extra

logger = logging.getLogger(__name__)


class USGSExtraction(BaseExtraction):
    """
    Handles data extraction from the USGS API
    """

    @classmethod
    def handle_extraction(  # type: ignore[reportIncompatibleMethodOverride]
        cls, url: str, params: dict | None, headers: dict | None, source: int, parent_id: int | None = None
    ) -> int:
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

            if response.status_code == 200 or response.status_code == 204:
                response_data = cls.store_extraction_data(
                    instance_id=instance.id,
                    source=ExtractionData.Source.USGS,
                    response=response,
                    validate_source_func=None,
                )
                # Check if response contains data
                if response_data:
                    cls._update_instance_status(instance, ExtractionData.Status.SUCCESS)
                    logger.info("Data extracted successfully")
                else:
                    cls._update_instance_status(
                        instance,
                        ExtractionData.Status.SUCCESS,
                        ExtractionData.ValidationStatus.NO_DATA,
                        update_validation=True,
                    )
                    logger.warning("No data found in response")
                    # FIXME: Should we return None?
                    return None
            return instance.id
        except requests.exceptions.RequestException:
            cls._update_instance_status(instance, ExtractionData.Status.FAILED)
            logger.error(
                "Extraction failed",
                exc_info=True,
                extra=log_extra({"source": instance.source}),
            )
            raise

    @staticmethod
    @app.task(queue=CeleryQueue.USGS_EXTRACTION, rate_limit="60/m")
    def task(url: str, parent_id: int | None):  # type: ignore[reportIncompatibleMethodOverride]
        """USGS Task"""
        details_id = USGSExtraction.handle_extraction(
            url=url, params=None, headers=None, parent_id=parent_id, source=ExtractionData.Source.USGS
        )

        if details_id:
            usgs_instance = ExtractionData.objects.get(id=details_id)
            with usgs_instance.resp_data.open() as file_data:
                detail_data = json.loads(file_data.read())
            if "losspager" in detail_data["properties"]["products"]:
                for item in detail_data["properties"]["products"]["losspager"]:
                    url = item["contents"]["json/losses.json"]["url"]
                    USGSExtraction.handle_extraction(
                        url=url,
                        params=None,
                        headers=None,
                        parent_id=details_id,
                        source=ExtractionData.Source.USGS.value,
                    )
        return details_id
