import strawberry
import strawberry_django

from apps.etl.enums import (
    ExtractionDataStatusTypeEnum,
    ExtractionSourceTypeEnum,
)
from apps.etl.models import ExtractionData


@strawberry_django.filters.filter(ExtractionData, lookups=True)
class ExtractionDataFilter:
    created_at: strawberry.auto
    source: ExtractionSourceTypeEnum
    status: ExtractionDataStatusTypeEnum
