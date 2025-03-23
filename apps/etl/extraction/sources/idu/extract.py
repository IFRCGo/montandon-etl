import logging

from apps.etl.extraction.sources.base.handler import BaseExtraction
from apps.etl.models import ExtractionData
from main.celery import app
from main.configs import etl_config

logger = logging.getLogger(__name__)


class IDUExtraction(BaseExtraction):
    """
    Handles data extraction from the IDU API.
    """

    @staticmethod
    @app.task
    def task(url: str):  # type: ignore[reportIncompatibleMethodOverride]
        """IDU Task"""
        headers = {"accept": "application/json"}
        params = {"client_id": etl_config.IDMC_CLIENT_ID}
        return IDUExtraction.handle_extraction(url=url, params=params, headers=headers, source=ExtractionData.Source.IDU)
