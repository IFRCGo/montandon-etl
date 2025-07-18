import strawberry
import strawberry_django
from asgiref.sync import sync_to_async
from django.db.models import Count, IntegerField, OuterRef, Q, Subquery, Value
from django.db.models.functions import Coalesce
from strawberry_django.pagination import OffsetPaginated
from strawberry_django.permissions import IsAuthenticated

from apps.etl.filters import ExtractionDataFilter, PystacDataFilter, TransformDataFilter
from apps.etl.models import ExtractionData, PyStacLoadData, Status, Transform
from apps.etl.orders import ExtractionOrder, PystacOrder, TransformOrder
from apps.etl.types import (
    CountbytraceID,
    ETLWithTraceID,
    ItemsbySource,
    ItemTypeSourceStatusSummary,
    RawExtractiondatatype,
    RawPystacdatatype,
    RawTransformdatatype,
    StatusCountExtraction,
    StatusCountTransform,
    StatusSourceCountExtraction,
    StatusSourceCountPyStac,
    StatusSourceCountPystacByItem,
    StatusSourceCountTransform,
    UniqueCounts,
    ValStatusSourceCount,
)
from main.graphql.context import Info


@strawberry.type
class Query:
    extraction: RawExtractiondatatype = strawberry_django.field(extensions=[IsAuthenticated()])

    extractions: OffsetPaginated[RawExtractiondatatype] = strawberry_django.offset_paginated(
        order=ExtractionOrder,
        filters=ExtractionDataFilter,
        extensions=[IsAuthenticated()],
    )

    transform: RawTransformdatatype = strawberry_django.field(extensions=[IsAuthenticated()])

    transforms: OffsetPaginated[RawTransformdatatype] = strawberry_django.offset_paginated(
        order=TransformOrder,
        filters=TransformDataFilter,
        extensions=[IsAuthenticated()],
    )

    pystac: RawPystacdatatype = strawberry_django.field(extensions=[IsAuthenticated()])

    pystacs: OffsetPaginated[RawPystacdatatype] = strawberry_django.offset_paginated(
        order=PystacOrder,
        filters=PystacDataFilter,
        extensions=[IsAuthenticated()],
    )

    extractionoftraceid: ETLWithTraceID = strawberry_django.field(extensions=[IsAuthenticated()])

    @strawberry.field()
    async def status_count_extraction(self, info: Info) -> list[StatusCountExtraction]:
        query_total_count = await sync_to_async(
            lambda: StatusCountExtraction.get_queryset(None, None, info).aggregate(
                in_progress_count=Count("id", filter=Q(status=Status.IN_PROGRESS)),
                success_count=Count("id", filter=Q(status=Status.SUCCESS)),
                failed_count=Count("id", filter=Q(status=Status.FAILED)),
                pending_count=Count("id", filter=Q(status=Status.PENDING)),
            )
        )()

        return [
            StatusCountExtraction(
                in_progress_count=query_total_count["in_progress_count"],
                success_count=query_total_count["success_count"],
                failed_count=query_total_count["failed_count"],
                pending_count=query_total_count["pending_count"],
            )
        ]

    @strawberry.field()
    async def status_source_counts_extraction(self, info: Info) -> list[StatusSourceCountExtraction]:
        query_countby_status_source = (
            StatusSourceCountExtraction.get_queryset(None, None, info)
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
            StatusSourceCountExtraction(
                source=item["source"],
                in_progress_count=item["in_progress_count"],
                success_count=item["success_count"],
                failed_count=item["failed_count"],
                pending_count=item["pending_count"],
            )
            for item in results
        ]

    @strawberry.field()
    async def validation_status_source_counts(self, info: Info) -> list[ValStatusSourceCount]:
        query_countby_valstatus_source = (
            ValStatusSourceCount.get_queryset(None, None, info)
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
            ValStatusSourceCount(
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
    async def count_trace_id(self, info: Info) -> list[CountbytraceID]:
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
    async def status_count_transform(self, info: Info) -> list[StatusCountTransform]:
        query_total_count = await sync_to_async(
            lambda: StatusCountTransform.get_queryset(None, None, info).aggregate(
                in_progress_count=Count("id", filter=Q(status=Status.IN_PROGRESS)),
                success_count=Count("id", filter=Q(status=Status.SUCCESS)),
                failed_count=Count("id", filter=Q(status=Status.FAILED)),
                pending_count=Count("id", filter=Q(status=Status.PENDING)),
            )
        )()

        return [
            StatusCountTransform(
                in_progress_count=query_total_count["in_progress_count"],
                success_count=query_total_count["success_count"],
                failed_count=query_total_count["failed_count"],
                pending_count=query_total_count["pending_count"],
            )
        ]

    @strawberry.field()
    async def status_source_counts_transform(self, info: Info) -> list[StatusSourceCountTransform]:
        query_countby_status_source = (
            StatusSourceCountTransform.get_queryset(None, None, info)
            .values("extraction__source")  # group by source
            .annotate(
                in_progress_count=Count("id", filter=Q(status=Status.IN_PROGRESS)),
                success_count=Count("id", filter=Q(status=Status.SUCCESS)),
                failed_count=Count("id", filter=Q(status=Status.FAILED)),
                pending_count=Count("id", filter=Q(status=Status.PENDING)),
            )
        )
        results = await sync_to_async(list)(query_countby_status_source)

        return [
            StatusSourceCountTransform(
                source=item["extraction__source"],
                in_progress_count=item["in_progress_count"],
                success_count=item["success_count"],
                failed_count=item["failed_count"],
                pending_count=item["pending_count"],
            )
            for item in results
        ]

    @strawberry.field()
    async def unique_items_counts(self, info: Info) -> list[UniqueCounts]:
        unique_counts = await sync_to_async(
            lambda: UniqueCounts.get_queryset(None, None, info).aggregate(
                events_count=Count("item_id", filter=Q(item_type=1), distinct=True),
                hazards_count=Count("item_id", filter=Q(item_type=2), distinct=True),
                impacts_count=Count("item_id", filter=Q(item_type=3), distinct=True),
            )
        )()

        return [
            UniqueCounts(
                unique_event_count=unique_counts["events_count"],
                unique_hazard_count=unique_counts["hazards_count"],
                unique_impact_count=unique_counts["impacts_count"],
            )
        ]

    @strawberry.field()
    async def items_counts_by_source(self, info: Info) -> list[ItemsbySource]:
        result = (
            ItemsbySource.get_queryset(None, None, info)
            .select_related("transform_id__extraction")
            .values("transform_id__extraction__source")
            .annotate(
                events_count=Count("item_id", filter=Q(item_type=1)),
                hazards_count=Count("item_id", filter=Q(item_type=2)),
                impacts_count=Count("item_id", filter=Q(item_type=3)),
            )
        )

        return [
            ItemsbySource(
                source=item["transform_id__extraction__source"],
                event_items=item["events_count"],
                hazard_items=item["hazards_count"],
                impact_items=item["impacts_count"],
            )
            async for item in result
        ]

    @strawberry.field()
    async def extraction_by_trace_id(self, info: Info, trace_id: int) -> list[ETLWithTraceID]:
        """
        Return ExtractionData, Transform, and PyStacLoadData objects that share a trace_id.
        """
        extraction_data = await sync_to_async(ExtractionData.objects.filter)(trace_id=trace_id)
        transforms = await sync_to_async(Transform.objects.filter)(trace_id=trace_id)
        pystac_data = await sync_to_async(PyStacLoadData.objects.filter)(trace_id=trace_id)
        return [
            ETLWithTraceID(
                extractions=extraction_data,
                transforms=transforms,
                pystacs=pystac_data,
            )
        ]

    @strawberry.field()
    async def status_source_counts_pystac(self, info: Info) -> list[StatusSourceCountPyStac]:
        query_countby_status_source = (
            StatusSourceCountPyStac.get_queryset(None, None, info)
            .values("transform_id__extraction__source")  # group by source
            .annotate(
                in_progress_count=Count("id", filter=Q(status=Status.IN_PROGRESS)),
                success_count=Count("id", filter=Q(status=Status.SUCCESS)),
                failed_count=Count("id", filter=Q(status=Status.FAILED)),
                pending_count=Count("id", filter=Q(status=Status.PENDING)),
            )
        )
        results = await sync_to_async(list)(query_countby_status_source)

        return [
            StatusSourceCountPyStac(
                source=item["transform_id__extraction__source"],
                in_progress_count=item["in_progress_count"],
                success_count=item["success_count"],
                failed_count=item["failed_count"],
                pending_count=item["pending_count"],
            )
            for item in results
        ]

    @strawberry.field()
    async def status_source_counts_pystac_by_item(self, info: Info) -> list[StatusSourceCountPystacByItem]:
        query_countby_status_source = (
            StatusSourceCountPyStac.get_queryset(None, None, info)
            .values("transform_id__extraction__source")  # group by source
            .annotate(
                event_count=Count("id", filter=Q(item_type=PyStacLoadData.ItemType.EVENT)),
                hazard_count=Count("id", filter=Q(item_type=PyStacLoadData.ItemType.HAZARD)),
                impact_count=Count("id", filter=Q(item_type=PyStacLoadData.ItemType.IMPACT)),
            )
        )
        results = await sync_to_async(list)(query_countby_status_source)

        return [
            StatusSourceCountPystacByItem(
                event_count=item["event_count"],
                source=item["transform_id__extraction__source"],
                hazard_count=item["hazard_count"],
                impact_count=item["impact_count"],
            )
            for item in results
        ]

    @strawberry.field()
    async def status_counts_by_source_for_itemtype(
        self,
        info: Info,
    ) -> list[ItemTypeSourceStatusSummary]:
        results = (
            ItemTypeSourceStatusSummary.get_queryset(None, None, info)
            .values("item_type", "transform_id__extraction__source")  # group by source
            .annotate(
                success_count=Count("id", filter=Q(status=PyStacLoadData.Status.SUCCESS)),
                failed_count=Count("id", filter=Q(status=PyStacLoadData.Status.FAILED)),
                pending_count=Count("id", filter=Q(status=PyStacLoadData.Status.PENDING)),
                id=Count("id"),
            )
        )
        return [
            ItemTypeSourceStatusSummary(
                source=event["transform_id__extraction__source"],
                item_type=event["item_type"],
                success_count=event["success_count"],
                failed_count=event["failed_count"],
                pending_count=event["pending_count"],
                total=event["id"],
            )
            async for event in results
        ]
