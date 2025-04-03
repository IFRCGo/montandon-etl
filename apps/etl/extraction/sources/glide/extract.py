import logging

import pydantic

from apps.etl.extraction.sources.base.handler import BaseExtraction
from main.celery import app
from main.configs import etl_config

logger = logging.getLogger(__name__)


class GlideExtractionMetadata(pydantic.BaseModel):
    fromyear: int | None
    frommonth: int | None
    fromday: int | None
    toyear: int | None
    tomonth: int | None
    today: int | None
    events: str | None

    def get_params(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v is not None}


class GlideExtraction(BaseExtraction[GlideExtractionMetadata]):
    """
    Handles data extraction from the GLIDE API.
    """

    metadata_class = GlideExtractionMetadata

    def extract(self, extraction_object) -> int:
        params = self.metadata_class(**extraction_object.metadata)
        return self.run_get_request(
            extraction_object,
            f"{etl_config.GLIDE_URL}/glide/jsonglideset.jsp",
            params,
        )

    @staticmethod
    @app.task
    def task(extraction_id: int):  # type: ignore[reportIncompatibleMethodOverride]
        return GlideExtraction().handle(extraction_id)
