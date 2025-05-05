from typing import Optional

import strawberry
import strawberry_django

from apps.etl.enums import (
    DataStatusTypeEnum,
    SourceTypeEnum,
)
from apps.etl.models import ExtractionData, PyStacLoadData, Transform


@strawberry_django.filters.filter(ExtractionData, lookups=True)
class ExtractionDataFilter:
    created_at: strawberry.auto
    source: Optional[SourceTypeEnum]
    status: Optional[DataStatusTypeEnum]
    trace_id: strawberry.auto


@strawberry_django.filters.filter(Transform, lookups=True)
class TransformDataFilter:
    created_at: strawberry.auto
    status: Optional[DataStatusTypeEnum]
    trace_id: strawberry.auto


@strawberry_django.filters.filter(PyStacLoadData, lookups=True)
class PystacDataFilter:
    created_at: strawberry.auto
    status: Optional[DataStatusTypeEnum]
    trace_id: strawberry.auto
