import logging

import pydantic

from apps.etl.extraction.sources.base.handler import BaseExtraction
from main.celery import app

logger = logging.getLogger(__name__)


class GlideExtractionInputMetadata(pydantic.BaseModel):
    fromyear: int | None
    frommonth: int | None
    fromday: int | None
    toyear: int | None
    tomonth: int | None
    today: int | None
    events: str | None


class GlideExtraction(BaseExtraction):
    """
    Handles data extraction from the GLIDE API.
    """

    def extract(self, extraction_object) -> int:
        return self.extract_common(extraction_object)

    @staticmethod
    @app.task
    def task(extraction_id: int):  # type: ignore[reportIncompatibleMethodOverride]
        return GlideExtraction().handle(extraction_id)
