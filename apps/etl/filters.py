from typing import Optional

import strawberry
import strawberry_django

from apps.etl.enums import (
    DataStatusTypeEnum,
    SourceTypeEnum,
)
from apps.etl.models import ExtractionData


@strawberry_django.filters.filter(ExtractionData, lookups=True)
class ExtractionDataFilter:
    created_at: strawberry.auto
    source: Optional[SourceTypeEnum]
    status: Optional[DataStatusTypeEnum]
    trace_id: strawberry.auto
    created_at: strawberry.auto
