import strawberry
from django.db import models

from apps.etl.enums import ExtractionSourceTypeEnum
from apps.etl.models import ExtractionData
from main.graphql.context import Info
from utils.common import get_queryset_for_model


@strawberry.type
class StatusCount:
    in_progress_count: int
    success_count: int
    failed_count: int
    pending_count: int

    @staticmethod
    def get_queryset(_, queryset: models.QuerySet | None, info: Info):
        new_queryset = get_queryset_for_model(ExtractionData, queryset)
        return new_queryset


@strawberry.type()
class StatusSourceCount:
    source: ExtractionSourceTypeEnum
    in_progress_count: int
    success_count: int
    failed_count: int
    pending_count: int

    @staticmethod
    def get_queryset(_, queryset: models.QuerySet | None, info: Info):
        new_queryset = get_queryset_for_model(ExtractionData, queryset)
        return new_queryset


@strawberry.type()
class ValStatusSourceCount:
    source: ExtractionSourceTypeEnum
    success_count: int
    failed_count: int
    no_data_count: int
    no_change_count: int
    no_validation_count: int

    @staticmethod
    def get_queryset(_, queryset: models.QuerySet | None, info: Info):
        new_queryset = get_queryset_for_model(ExtractionData, queryset)
        return new_queryset


@strawberry.type()
class CountbytraceID:
    source: ExtractionSourceTypeEnum
    extraction_count: int
    transform_count: int
    stac_count: int
