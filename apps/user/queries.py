import strawberry
import strawberry_django
from asgiref.sync import sync_to_async
from strawberry_django.pagination import OffsetPaginated
from strawberry_django.permissions import IsAuthenticated

from main.graphql.context import Info

from .filters import UserFilter
from .orders import UserOrder
from .types import UserMeType, UserType


@strawberry.type
class Query:
    # Public --------------------
    @strawberry.field
    @sync_to_async
    def me(self, info: Info) -> UserMeType | None:
        user = info.context.request.user
        if user.is_authenticated:
            return user  # type: ignore[reportGeneralTypeIssues]
        return None

    # Private --------------------
    # --- Paginated
    users: OffsetPaginated[UserType] = strawberry_django.offset_paginated(
        order=UserOrder,
        filters=UserFilter,
        extensions=[IsAuthenticated()],
    )
