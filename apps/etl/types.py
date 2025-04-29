import strawberry
from django.db import models

from apps.etl.enums import ExtractionSourceTypeEnum, ExtractionDataStatusTypeEnum, ExtractionValidationTypeEnum
from apps.etl.models import ExtractionData
from main.graphql.context import Info
from utils.common import get_queryset_for_model
class ExtractionDataQuerysetMixin:
    @staticmethod
    def get_queryset(_, queryset: models.QuerySet | None, info: Info):
        return get_queryset_for_model(ExtractionData, queryset)

@strawberry.type
class RawExtractiondata(ExtractionDataQuerysetMixin):
    status: ExtractionDataStatusTypeEnum
    source: ExtractionSourceTypeEnum
    source_validation_status: ExtractionValidationTypeEnum

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


@strawberry.type()
class ValStatusSourceCount(ExtractionDataQuerysetMixin):
    source: ExtractionSourceTypeEnum
    success_count: int
    failed_count: int
    no_data_count: int
    no_change_count: int
    no_validation_count: int

@strawberry.type()
class CountbytraceID:
    source: ExtractionSourceTypeEnum
    extraction_count: int
    transform_count: int
    stac_count: int
