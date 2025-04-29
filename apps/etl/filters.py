import strawberry
import strawberry_django

from apps.etl.enums import (
    ExtractionDataStatusTypeEnum,
    ExtractionSourceTypeEnum,
    PyStacLoadDataItemTypeEnum,
    PyStacLoadDataStatusEnum,
)
from apps.etl.models import ExtractionData, PyStacLoadData


@strawberry_django.filters.filter(PyStacLoadData, lookups=True)
class PyStacLoadDataFilter:
    id: strawberry.auto
    status: PyStacLoadDataStatusEnum
    item_type: PyStacLoadDataItemTypeEnum
    trace_id: int


@strawberry_django.filters.filter(ExtractionData, lookups=True)
class ExtractionDataFilter:
    created_at: strawberry.auto
    source: ExtractionSourceTypeEnum
    status: ExtractionDataStatusTypeEnum


@strawberry_django.filters.filter(ExtractionData, lookups=True)
class TestFilter:
    source: ExtractionSourceTypeEnum
    status: ExtractionDataStatusTypeEnum
