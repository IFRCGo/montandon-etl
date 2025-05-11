import strawberry
import strawberry_django
from asgiref.sync import sync_to_async
from django.db.models import Count, IntegerField, OuterRef, Q, Subquery, Value
from django.db.models.functions import Coalesce
from strawberry_django.pagination import OffsetPaginated
from strawberry_django.permissions import IsAuthenticated

from apps.etl.graphql.filters import ExtractionDataFilter, PystacDataFilter, TransformDataFilter
from apps.etl.graphql.orders import ExtractionOrder, PystacOrder, TransformOrder
from apps.etl.graphql.types import (
    CountbytraceID,
    ExtractionCountByStatus,
    ExtractionCountByStatusAndSource,
    ExtractionCountByValStatusAndSource,
    Extractiontype,
    Pystactype,
    TransformCountByStatus,
    TransformCountByStatusAndSource,
    Transformtype,
)
from apps.etl.models import ExtractionData, PyStacLoadData, Status, Transform
from main.graphql.context import Info


@strawberry.type
class Query:
    extraction: Extractiontype = strawberry_django.field(extensions=[IsAuthenticated()])

    extractions: OffsetPaginated[Extractiontype] = strawberry_django.offset_paginated(
        order=ExtractionOrder,
        filters=ExtractionDataFilter,
        extensions=[IsAuthenticated()],
    )

    transform: Transformtype = strawberry_django.field(extensions=[IsAuthenticated()])

    transforms: OffsetPaginated[Transformtype] = strawberry_django.offset_paginated(
        order=TransformOrder,
        filters=TransformDataFilter,
        extensions=[IsAuthenticated()],
    )

    pystac: Pystactype = strawberry_django.field(extensions=[IsAuthenticated()])

    pystacs: OffsetPaginated[Pystactype] = strawberry_django.offset_paginated(
        order=PystacOrder,
        filters=PystacDataFilter,
        extensions=[IsAuthenticated()],
    )

    @strawberry.field()
    async def extraction_count_by_status(self, info: Info) -> list[ExtractionCountByStatus]:
        query_total_count = await sync_to_async(
            lambda: ExtractionCountByStatus.get_queryset(None, None, info).aggregate(
                in_progress_count=Count("id", filter=Q(status=Status.IN_PROGRESS)),
                success_count=Count("id", filter=Q(status=Status.SUCCESS)),
                failed_count=Count("id", filter=Q(status=Status.FAILED)),
                pending_count=Count("id", filter=Q(status=Status.PENDING)),
            )
        )()

        return [
            ExtractionCountByStatus(
                in_progress_count=query_total_count["in_progress_count"],
                success_count=query_total_count["success_count"],
                failed_count=query_total_count["failed_count"],
                pending_count=query_total_count["pending_count"],
            )
        ]

    @strawberry.field()
    async def extraction_count_by_status_source(self, info: Info) -> list[ExtractionCountByStatusAndSource]:
        query_countby_status_source = (
            ExtractionCountByStatusAndSource.get_queryset(None, None, info)
            .values("source")  # group by source
            .annotate(
                in_progress_count=Count("id", filter=Q(status=Status.IN_PROGRESS)),
                success_count=Count("id", filter=Q(status=Status.SUCCESS)),
                failed_count=Count("id", filter=Q(status=Status.FAILED)),
                pending_count=Count("id", filter=Q(status=Status.PENDING)),
            )
        )
        results = await sync_to_async(list)(query_countby_status_source)

        return [
            ExtractionCountByStatusAndSource(
                source=item["source"],
                in_progress_count=item["in_progress_count"],
                success_count=item["success_count"],
                failed_count=item["failed_count"],
                pending_count=item["pending_count"],
            )
            for item in results
        ]

    @strawberry.field()
    async def extraction_count_by_valstatus_source(self, info: Info) -> list[ExtractionCountByValStatusAndSource]:
        query_countby_valstatus_source = (
            ExtractionCountByValStatusAndSource.get_queryset(None, None, info)
            .values("source")  # group by source
            .annotate(
                success_count=Count("id", filter=Q(source_validation_status=ExtractionData.ValidationStatus.SUCCESS)),
                failed_count=Count("id", filter=Q(source_validation_status=ExtractionData.ValidationStatus.FAILED)),
                no_data_count=Count("id", filter=Q(source_validation_status=ExtractionData.ValidationStatus.NO_DATA)),
                no_change_count=Count("id", filter=Q(source_validation_status=ExtractionData.ValidationStatus.NO_CHANGE)),
                no_validation_count=Count(
                    "id", filter=Q(source_validation_status=ExtractionData.ValidationStatus.NO_VALIDATION)
                ),
            )
        )
        return [
            ExtractionCountByValStatusAndSource(
                source=event["source"],
                success_count=event["success_count"],
                failed_count=event["failed_count"],
                no_data_count=event["no_data_count"],
                no_change_count=event["no_change_count"],
                no_validation_count=event["no_validation_count"],
            )
            async for event in query_countby_valstatus_source
        ]

    @strawberry.field()
    async def count_by_trace_id(self, info: Info) -> list[CountbytraceID]:
        final_counts = (
            PyStacLoadData.objects.filter(trace_id=OuterRef("trace_id"))
            .values("trace_id")
            .annotate(count=Count("id"))
            .values("count")[:1]
        )

        processing_counts = (
            Transform.objects.filter(trace_id=OuterRef("trace_id"))
            .values("trace_id")
            .annotate(count=Count("id"))
            .values("count")[:1]
        )

        qs = (
            CountbytraceID.get_queryset(None, None, info)
            .values("trace_id", "source")
            .annotate(
                extraction_count=Count("id"),
                transform_count=Coalesce(Subquery(processing_counts, output_field=IntegerField()), Value(0)),
                stac_count=Coalesce(Subquery(final_counts, output_field=IntegerField()), Value(0)),
            )
        )

        return [
            CountbytraceID(
                trace_id=item["trace_id"],
                source=item["source"],
                extraction_count=item["extraction_count"],
                transform_count=item["transform_count"],
                stac_count=item["stac_count"],
            )
            async for item in qs
        ]

    @strawberry.field()
    async def transform_count_by_status(self, info: Info) -> list[TransformCountByStatus]:
        query_total_count = await sync_to_async(
            lambda: TransformCountByStatus.get_queryset(None, None, info).aggregate(
                in_progress_count=Count("id", filter=Q(status=Status.IN_PROGRESS)),
                success_count=Count("id", filter=Q(status=Status.SUCCESS)),
                failed_count=Count("id", filter=Q(status=Status.FAILED)),
                pending_count=Count("id", filter=Q(status=Status.PENDING)),
            )
        )()

        return [
            TransformCountByStatus(
                in_progress_count=query_total_count["in_progress_count"],
                success_count=query_total_count["success_count"],
                failed_count=query_total_count["failed_count"],
                pending_count=query_total_count["pending_count"],
            )
        ]

    @strawberry.field()
    async def transform_count_by_status_source(self, info: Info) -> list[TransformCountByStatusAndSource]:
        query_countby_status_source = (
            TransformCountByStatusAndSource.get_queryset(None, None, info)
            .values("source")  # group by source
            .annotate(
                in_progress_count=Count("id", filter=Q(status=Status.IN_PROGRESS)),
                success_count=Count("id", filter=Q(status=Status.SUCCESS)),
                failed_count=Count("id", filter=Q(status=Status.FAILED)),
                pending_count=Count("id", filter=Q(status=Status.PENDING)),
            )
        )
        results = await sync_to_async(list)(query_countby_status_source)

        return [
            TransformCountByStatusAndSource(
                source=item["source"],
                in_progress_count=item["in_progress_count"],
                success_count=item["success_count"],
                failed_count=item["failed_count"],
                pending_count=item["pending_count"],
            )
            for item in results
        ]
