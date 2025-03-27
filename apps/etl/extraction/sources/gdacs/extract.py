import logging
from typing import Optional

import pydantic

from apps.etl.extraction.sources.base.handler import BaseExtraction
from apps.etl.models import ExtractionData
from main.celery import app

logger = logging.getLogger(__name__)


class GdacsExtractionInputMetadata(pydantic.BaseModel):
    fromDate: str
    toDate: str
    alertlevel: Optional[str] | None
    eventlist: str
    country: Optional[str] | None


class GdacsEventExtractionInputMetadata(pydantic.BaseModel):
    eventtype: Optional[str] | None
    eventid: Optional[int] | None
    episodeid: Optional[int] | None


class GdacsExtraction(BaseExtraction):
    """
    Handles data extraction from the Gdacs API.
    """

    @staticmethod
    @app.task
    def task(url: str, input_metadata_class: pydantic.BaseModel = None, metadata: dict = None, parent_id: int = None):  # type: ignore[reportIncompatibleMethodOverride]
        input_metadata = input_metadata_class(**metadata)
        return GdacsExtraction().handle_extraction(
            url=url,
            params=input_metadata.model_dump(),
            headers={"accept": "application/json"},
            source=ExtractionData.Source.GDACS.value,
            parent_id=parent_id,
        )
