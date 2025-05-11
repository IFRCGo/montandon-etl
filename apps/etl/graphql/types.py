import strawberry
import strawberry_django
from django.db import models
from strawberry import auto

from apps.etl.graphql.enums import DataStatusTypeEnum, ExtractionValidationTypeEnum, SourceTypeEnum
from apps.etl.models import ExtractionData, PyStacLoadData, Transform
from main.graphql.context import Info
from utils.common import get_queryset_for_model


class ExtractionDataQuerysetMixin:
    @staticmethod
    def get_queryset(_, queryset: models.QuerySet | None, info: Info):
        return get_queryset_for_model(ExtractionData, queryset)


class TransformDataQuerysetMixin:
    @staticmethod
    def get_queryset(_, queryset: models.QuerySet | None, info: Info):
        return get_queryset_for_model(Transform, queryset)


@strawberry_django.type(ExtractionData)
class Extractiontype:
    id: auto
    source: SourceTypeEnum
    status: DataStatusTypeEnum
    url: auto
    resp_code: auto
    resp_data_type: auto
    parent_id: auto = strawberry_django.field(only=["parent_id"])
    source_validation_status: ExtractionValidationTypeEnum
    hazard_type: auto
    trace_id: auto = strawberry_django.field(only=["trace_id"])


@strawberry_django.type(Transform)
class Transformtype:
    id: auto
    status: DataStatusTypeEnum
    trace_id: auto = strawberry_django.field(only=["trace_id"])
    metadata: auto
    extraction: auto
    created_at: auto
    started_at: auto
    ended_at: auto


@strawberry_django.type(PyStacLoadData)
class Pystactype:
    id: auto
    status: DataStatusTypeEnum
    trace_id: auto = strawberry_django.field(only=["trace_id"])
    item_type: auto
    created_at: auto
    modified_at: auto
    transform_id: auto


@strawberry.type
class ExtractionCountByStatus(ExtractionDataQuerysetMixin):
    in_progress_count: int
    success_count: int
    failed_count: int
    pending_count: int


@strawberry.type
class ExtractionCountByStatusAndSource(ExtractionDataQuerysetMixin):
    source: SourceTypeEnum
    in_progress_count: int
    success_count: int
    failed_count: int
    pending_count: int


@strawberry.type
class ExtractionCountByValStatusAndSource(ExtractionDataQuerysetMixin):
    source: SourceTypeEnum
    success_count: int
    failed_count: int
    no_data_count: int
    no_change_count: int
    no_validation_count: int


@strawberry.type
class CountbytraceID(ExtractionDataQuerysetMixin):
    source: SourceTypeEnum
    trace_id: int
    extraction_count: int
    transform_count: int
    stac_count: int


@strawberry.type
class TransformCountByStatus(TransformDataQuerysetMixin):
    in_progress_count: int
    success_count: int
    failed_count: int
    pending_count: int


@strawberry.type
class TransformCountByStatusAndSource(ExtractionDataQuerysetMixin):
    source: SourceTypeEnum
    in_progress_count: int
    success_count: int
    failed_count: int
    pending_count: int
