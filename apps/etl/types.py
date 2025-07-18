import strawberry
import strawberry_django
from django.db import models
from strawberry import auto

from apps.etl.enums import DataStatusTypeEnum, ExtractionValidationTypeEnum, PyStacLoadDataItemTypeEnum, SourceTypeEnum
from apps.etl.models import ExtractionData, PyStacLoadData, Transform
from main.graphql.context import Info
from utils.common import get_queryset_for_model, sync_to_async


class ExtractionDataQuerysetMixin:
    @staticmethod
    def get_queryset(_, queryset: models.QuerySet | None, info: Info):
        return get_queryset_for_model(ExtractionData, queryset)


class TransformDataQuerysetMixin:
    @staticmethod
    def get_queryset(_, queryset: models.QuerySet | None, info: Info):
        return get_queryset_for_model(Transform, queryset)


class PyStacDataQuerysetMixin:
    @staticmethod
    def get_queryset(_, queryset: models.QuerySet | None, info: Info):
        return get_queryset_for_model(PyStacLoadData, queryset)


@strawberry_django.type(ExtractionData)
class RawExtractiondatatype:
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

    @strawberry.field
    @sync_to_async
    def filesize(self, info: Info) -> float:
        return round(self.resp_data.size / (1024), 2) if self.resp_data else 0


@strawberry_django.type(Transform)
class RawTransformdatatype:
    id: auto
    status: DataStatusTypeEnum
    trace_id: auto = strawberry_django.field(only=["trace_id"])
    metadata: auto
    extraction: auto = strawberry_django.field(only=["extraction"])
    created_at: auto
    started_at: auto
    ended_at: auto

    @strawberry.field
    @sync_to_async
    def source(self, info: Info) -> SourceTypeEnum:
        return SourceTypeEnum(self.extraction.source)


@strawberry_django.type(PyStacLoadData)
class RawPystacdatatype:
    id: auto
    status: DataStatusTypeEnum
    trace_id: auto = strawberry_django.field(only=["trace_id"])
    item_type: PyStacLoadDataItemTypeEnum
    created_at: auto
    modified_at: auto
    item: auto
    collection_id: auto
    transform_id: auto = strawberry_django.field(only=["transform_id"])

    @strawberry.field
    @sync_to_async
    def source(self, info: Info) -> SourceTypeEnum:
        return SourceTypeEnum(self.transform_id.extraction.source)


@strawberry.type
class StatusCountExtraction(ExtractionDataQuerysetMixin):
    in_progress_count: int
    success_count: int
    failed_count: int
    pending_count: int


@strawberry.type
class StatusSourceCountExtraction(ExtractionDataQuerysetMixin):
    source: SourceTypeEnum
    in_progress_count: int
    success_count: int
    failed_count: int
    pending_count: int


@strawberry.type
class ValStatusSourceCount(ExtractionDataQuerysetMixin):
    source: SourceTypeEnum
    success_count: int
    failed_count: int
    no_data_count: int
    no_change_count: int
    no_validation_count: int


@strawberry.type
class ItemTypeSourceStatusSummary(PyStacDataQuerysetMixin):
    source: SourceTypeEnum
    success_count: int
    failed_count: int
    pending_count: int
    item_type: PyStacLoadDataItemTypeEnum
    total: int


@strawberry.type
class CountbytraceID(ExtractionDataQuerysetMixin):
    source: SourceTypeEnum
    trace_id: int
    extraction_count: int
    transform_count: int
    stac_count: int


@strawberry.type
class StatusCountTransform(TransformDataQuerysetMixin):
    in_progress_count: int
    success_count: int
    failed_count: int
    pending_count: int


@strawberry.type
class StatusSourceCountTransform(TransformDataQuerysetMixin):
    source: SourceTypeEnum
    in_progress_count: int
    success_count: int
    failed_count: int
    pending_count: int


@strawberry.type
class RetriggerResponse:
    trace_id: int


@strawberry.type
class UniqueCounts(PyStacDataQuerysetMixin):
    unique_hazard_count: int
    unique_event_count: int
    unique_impact_count: int


@strawberry.type
class ItemsbySource(PyStacDataQuerysetMixin):
    source: SourceTypeEnum
    event_items: int
    hazard_items: int
    impact_items: int


@strawberry.type
class ETLWithTraceID:
    extractions: list[RawExtractiondatatype]
    transforms: list[RawTransformdatatype]
    pystacs: list[RawPystacdatatype]


@strawberry.type
class StatusSourceCountPyStac(PyStacDataQuerysetMixin):
    source: SourceTypeEnum
    in_progress_count: int
    success_count: int
    failed_count: int
    pending_count: int


@strawberry.type
class StatusSourceCountPystacByItem(PyStacDataQuerysetMixin):
    source: SourceTypeEnum
    event_count: int
    hazard_count: int
    impact_count: int


@strawberry.type
class PystacItembyItemType(PyStacDataQuerysetMixin):
    source: SourceTypeEnum
    event_count: int
    hazard_count: int
    impact_count: int
