import strawberry
from strawberry.types import Info
from asgiref.sync import sync_to_async

from apps.common.types import UserMeType
from apps.etl.types import ExtractionDataType
from main.graphql.paginations import CountList, pagination_field
from .filters import ExtractionDataFilter


@strawberry.type
class PrivateQuery:
    extraction_list: CountList[ExtractionDataType] = pagination_field(
        pagination=True,
        filters=ExtractionDataFilter,
    )

    @strawberry.field
    @sync_to_async
    def me(self, info: Info) -> UserMeType | None:
        user = info.context.request.user
        if user.is_authenticated:
            return user  # type: ignore[reportGeneralTypeIssues]
