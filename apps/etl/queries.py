import strawberry
from asgiref.sync import sync_to_async
from django.db.models import Count, IntegerField, OuterRef, Q, Subquery, Value
from django.db.models.functions import Coalesce

from apps.etl.filters import ExtractionDataFilter
from apps.etl.models import ExtractionData, PyStacLoadData, Status, Transform
from apps.etl.types import (
    CountbytraceID,
    RawExtractiondatatype,
    StatusCountExtraction,
    StatusCountTransform,
    StatusSourceCountExtraction,
    StatusSourceCountTransform,
    ValStatusSourceCount,
)
from main.graphql.context import Info
from utils.strawberry.paginations import CountList, pagination_field


@strawberry.type
class PrivateQuery:
    extraction_list: CountList[RawExtractiondatatype] = pagination_field(
        pagination=True,
        filters=ExtractionDataFilter,
    )

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

    # @strawberry.field()
    # async def count_trace_id(self, info: Info) -> list[CountbytraceID]:

    #     @sync_to_async
    #     def get_trace_counts():
    #         final_counts = dict(
    #             PyStacLoadData.objects
    #             .values('trace_id')
    #             .annotate(final_count=Count('id'))
    #             .values_list('trace_id', "final_count")
    #         )

    #         processing_counts = dict(
    #             Transform.objects
    #             .values('trace_id')
    #             .annotate(processing_count=Count('id'))
    #             .values_list('trace_id', "processing_count")
    #         )

    #         qs = CountbytraceID.get_queryset(None, None, info).values(
    #             'trace_id', 'source'
    #         ).annotate(extraction_count=Count('id'))

    #         results = [
    #             CountbytraceID(
    #                 trace_id=item['trace_id'],
    #                 source=item['source'],
    #                 extraction_count=item['extraction_count'],
    #                 transform_count=processing_counts.get(item['trace_id'], 0),
    #                 stac_count=final_counts.get(item['trace_id'], 0),
    #             )
    #             for item in qs
    #         ]
    #         return results

    #     return await get_trace_counts()

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
            StatusSourceCountTransform(
                source=item["source"],
                in_progress_count=item["in_progress_count"],
                success_count=item["success_count"],
                failed_count=item["failed_count"],
                pending_count=item["pending_count"],
            )
            for item in results
        ]


@strawberry.type
class PublicQuery:
    noop: strawberry.ID = strawberry.ID("noop")
