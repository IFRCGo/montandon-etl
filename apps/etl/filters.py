import strawberry
from typing import Optional

from .models import ExtractionData
from .enums import (
    ExtractionDataStatusTypeEnum,
    ExtractionSourceTypeEnum,
)


@strawberry.django.filters.filter(ExtractionData)
class ExtractionDataFilter:
    source: Optional[ExtractionSourceTypeEnum]
    status: Optional[ExtractionDataStatusTypeEnum]
