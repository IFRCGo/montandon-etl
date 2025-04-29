from typing import Optional

import strawberry
import strawberry_django
from django.db import models
from strawberry import auto

from apps.etl.enums import ExtractionDataStatusTypeEnum, ExtractionSourceTypeEnum
from apps.etl.models import ExtractionData
from main.graphql.context import Info
from utils.common import get_queryset_for_model


class ExtractionDataQuerysetMixin:
    @staticmethod
    def get_queryset(_, queryset: models.QuerySet | None, info: Info):
        return get_queryset_for_model(ExtractionData, queryset)


@strawberry_django.type(ExtractionData)
class RawExtractiondatatype:
    id: auto
    source: ExtractionSourceTypeEnum
    status: ExtractionDataStatusTypeEnum
    url: auto
    resp_code: auto
    resp_data_type: auto
    parent_id: Optional[int]
    source_validation_status: auto
    hazard_type: auto
    trace_id: int

    def resolve_parent(self, root):
        return root.parent.id

    @staticmethod
    def get_queryset(_, queryset: models.QuerySet | None, info: Info):
        return get_queryset_for_model(ExtractionData, queryset)


@strawberry.type
class StatusCount(ExtractionDataQuerysetMixin):
    in_progress_count: int
    success_count: int
    failed_count: int
    pending_count: int


@strawberry.type
class StatusSourceCount(ExtractionDataQuerysetMixin):
    source: ExtractionSourceTypeEnum
    in_progress_count: int
    success_count: int
    failed_count: int
    pending_count: int


@strawberry.type
class ValStatusSourceCount(ExtractionDataQuerysetMixin):
    source: ExtractionSourceTypeEnum
    success_count: int
    failed_count: int
    no_data_count: int
    no_change_count: int
    no_validation_count: int


@strawberry.type
class CountbytraceID:
    source: ExtractionSourceTypeEnum
    extraction_count: int
    transform_count: int
    stac_count: int
