from typing import Optional

import strawberry

from .enums import ExtractionDataStatusTypeEnum, ExtractionSourceTypeEnum
from .models import ExtractionData


@strawberry.django.filters.filter(ExtractionData)
class ExtractionDataFilter:
    source: Optional[ExtractionSourceTypeEnum]
    status: Optional[ExtractionDataStatusTypeEnum]
