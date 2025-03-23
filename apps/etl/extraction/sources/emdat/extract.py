import logging
import typing

import requests

from apps.etl.extraction.sources.base.handler import BaseExtraction
from apps.etl.models import ExtractionData
from main.celery import app
from main.configs import etl_config
from main.logging import log_extra

logger = logging.getLogger(__name__)

EMDATQueryVars = typing.TypedDict(
    "EMDATQueryVars",
    {
        "limit": int | None,
        "from": int | None,
        "to": int | None,
        "include_hist": bool | None,
    },
)


class EMDATExtraction(BaseExtraction):
    """
    Handles data extraction from the EMDAT API.
    """

    # FIXME: We need to handle GraphQL request in BaseExtraction
    @classmethod
    def handle_extraction(cls, query: str, variables: EMDATQueryVars, source: int) -> int:  # type: ignore[reportIncompatibleMethodOverride]
        """
        Process data extraction.
        Returns:
            int: ID of the extraction instance
        """
        logger.info("Starting data extraction")

        url = f"{etl_config.EMDAT_URL}/v1"
        headers = {"Authorization": etl_config.EMDAT_AUTHORIZATION_KEY}

        instance = cls._create_extraction_instance(url=url, source=source)

        try:
            cls._update_instance_status(instance, ExtractionData.Status.IN_PROGRESS)

            paylod = {"query": query, "variables": variables}
            response = requests.post(url, json=paylod, headers=headers)
            response.raise_for_status()
            response_data = cls._save_response_data(instance, response)

            # FIXME: Handle response.status_code == 200 or response.status_code == 204:
            if not response_data or not response_data["data"]["public_emdat"]:
                cls._update_instance_status(
                    instance,
                    ExtractionData.Status.SUCCESS,
                    ExtractionData.ValidationStatus.NO_DATA,
                    update_validation=True,
                )
                logger.warning("No hazard data found in response")
            else:
                cls._update_instance_status(instance, ExtractionData.Status.SUCCESS)

            return instance.id

        except requests.exceptions.RequestException:
            cls._update_instance_status(instance, ExtractionData.Status.FAILED)
            logger.error("Extraction failed", exc_info=True, extra=log_extra({"source": ExtractionData.Source.EMDAT}))
            raise

    @staticmethod
    @app.task
    def task(query: str, variables: EMDATQueryVars):  # type: ignore[reportIncompatibleMethodOverride]
        return EMDATExtraction().handle_extraction(query, variables, ExtractionData.Source.EMDAT)
