from typing import Optional

import strawberry
import strawberry_django
from django.db import models

from .enums import ExtractionDataStatusTypeEnum, ExtractionSourceTypeEnum
from .models import ExtractionData


@strawberry_django.filters.filter(ExtractionData, lookups=True)
class ExtractionDataFilter:
    source: Optional[ExtractionSourceTypeEnum]
    status: Optional[ExtractionDataStatusTypeEnum]
    created_at: strawberry.auto

    @strawberry_django.filter_field
    def created_at_lte(
        self,
        queryset: models.QuerySet,
        value: strawberry.ID,
        prefix: str,
    ) -> tuple[models.QuerySet, models.Q]:

        return queryset, models.Q(**{f"{prefix}created_at__lte": value})

    @strawberry_django.filter_field
    def created_at_gte(
        self,
        queryset: models.QuerySet,
        value: strawberry.ID,
        prefix: str,
    ) -> tuple[models.QuerySet, models.Q]:

        return queryset, models.Q(**{f"{prefix}created_at__gte": value})
