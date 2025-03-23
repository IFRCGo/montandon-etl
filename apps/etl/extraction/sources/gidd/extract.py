from apps.etl.extraction.sources.base.handler import BaseExtraction
from apps.etl.models import ExtractionData
from main.celery import app
from main.configs import etl_config


class GIDDExtraction(BaseExtraction):
    """
    Handles data extraction from the GIDD API.
    """

    @staticmethod
    @app.task
    def task():  # type: ignore[reportIncompatibleMethodOverride]
        url = f"{etl_config.IDMC_DATA_URL}/external-api/gidd/disaggregations/disaggregation-geojson/"
        headers = {"accept": "application/json"}
        params = {"client_id": etl_config.IDMC_CLIENT_ID}
        return GIDDExtraction().handle_extraction(url, params, headers, ExtractionData.Source.GIDD)
