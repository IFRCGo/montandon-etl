from django.conf import settings

from apps.etl.extraction.sources.base.handler import BaseExtraction
from apps.etl.models import ExtractionData
from main.celery import app

DATA_URL = f"{settings.IDMC_DATA_URL}/external-api/gidd/disaggregations/disaggregation-geojson/"
HEADERS = {"accept": "application/json"}
PARAMS = {"client_id": settings.IDMC_CLIENT_ID}


class GIDDExtraction(BaseExtraction):
    """
    Handles data extraction from the GIDD API.
    """

    @staticmethod
    @app.task
    def task():
        return GIDDExtraction().handle_extraction(DATA_URL, PARAMS, HEADERS, ExtractionData.Source.GIDD)
