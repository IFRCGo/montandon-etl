import pydantic

from apps.etl.extraction.sources.base.handler import BaseExtraction
from apps.etl.models import ExtractionData
from main.celery import app
from main.configs import etl_config


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

    @staticmethod
    @app.task
    def task(metadata: dict):  # type: ignore[reportIncompatibleMethodOverride]
        input_metadata = GlideExtractionInputMetadata(**metadata)
        return GlideExtraction().handle_extraction(
            url=f"{etl_config.GLIDE_URL}/glide/jsonglideset.jsp",
            params=input_metadata.model_dump(),
            headers={"accept": "application/json"},
            source=ExtractionData.Source.GLIDE.value,
        )
