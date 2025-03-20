import logging

from django.conf import settings

from apps.etl.extraction.sources.base.handler import BaseExtraction
from apps.etl.models import ExtractionData
from main.celery import app

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
        params = {"client_id": settings.IDMC_CLIENT_ID}
        return IDUExtraction.handle_extraction(url=url, params=params, headers=headers, source=ExtractionData.Source.IDU)
