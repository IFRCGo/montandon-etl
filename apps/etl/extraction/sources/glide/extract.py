import typing

from apps.etl.extraction.sources.base.handler import BaseExtraction
from apps.etl.models import ExtractionData
from main.celery import app

HEADERS = {"accept": "application/json"}

GlideQueryVars = typing.TypedDict(
    "GlideQueryVars",
    {
        "fromyear": int | None,
        "frommonth": int | None,
        "fromday": int | None,
        "toyear": int | None,
        "tomonth": int | None,
        "today": int | None,
        "events": str | None,
    },
)


class GlideExtraction(BaseExtraction):
    """
    Handles data extraction from the GLIDE API.
    """

    @staticmethod
    @app.task
    def task(url: str, variables: GlideQueryVars):  # type: ignore[reportIncompatibleMethodOverride]
        return GlideExtraction().handle_extraction(url, variables, HEADERS, ExtractionData.Source.GLIDE)
