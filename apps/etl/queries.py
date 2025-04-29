import strawberry
from asgiref.sync import sync_to_async
from django.db.models import Count, Q

from apps.etl.models import ExtractionData, Status
from apps.etl.types import RawExtractiondata, StatusCount, StatusSourceCount, ValStatusSourceCount
from main.graphql.context import Info


@strawberry.type
class PublicQuery:
    @strawberry.field()
    async def all_extraction_data(self, info: Info) -> list[RawExtractiondata]:
        qs = RawExtractiondata.get_queryset(None, None, info).order_by("id")
        return [data async for data in qs]

    @strawberry.field()
    async def total_count(self, info: Info) -> list[StatusCount]:
        query_total_count = await sync_to_async(
            lambda: StatusCount.get_queryset(None, None, info).aggregate(
                in_progress_count=Count("id", filter=Q(status=Status.IN_PROGRESS)),
                success_count=Count("id", filter=Q(status=Status.SUCCESS)),
                failed_count=Count("id", filter=Q(status=Status.FAILED)),
                pending_count=Count("id", filter=Q(status=Status.PENDING)),
            )
        )()

        return [
            StatusCount(
                in_progress_count=query_total_count["in_progress_count"],
                success_count=query_total_count["success_count"],
                failed_count=query_total_count["failed_count"],
                pending_count=query_total_count["pending_count"],
            )
        ]

    @strawberry.field()
    async def status_source_counts(self, info: Info) -> list[StatusSourceCount]:
        query_countby_status_source = (
            StatusSourceCount.get_queryset(None, None, info)
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
            StatusSourceCount(
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
