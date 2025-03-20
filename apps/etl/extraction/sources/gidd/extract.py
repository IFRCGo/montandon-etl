from django.conf import settings

from apps.etl.extraction.sources.base.handler import BaseExtraction
from apps.etl.models import ExtractionData
from main.celery import app


class GIDDExtraction(BaseExtraction):
    """
    Handles data extraction from the GIDD API.
    """

    @staticmethod
    @app.task
    def task():
        url = f"{settings.IDMC_DATA_URL}/external-api/gidd/disaggregations/disaggregation-geojson/"
        headers = {"accept": "application/json"}
        params = {"client_id": settings.IDMC_CLIENT_ID}
        return GIDDExtraction().handle_extraction(url, params, headers, ExtractionData.Source.GIDD)
