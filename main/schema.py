import strawberry
from strawberry.types import Info

from apps.common.types import UserMeType
from apps.etl.types import ExtractionDataListType, ExtractionDataType


@strawberry.type
class Query:
    extraction_data_list: list[ExtractionDataListType] = strawberry.django.field()
    extraction_data: ExtractionDataType = strawberry.django.field()
    # me: UserMeType = strawberry.django.field()

    @strawberry.field
    def me(self, info: Info) -> UserMeType:
        user = info.context["request"].user
        if user.is_authenticated:
            return UserMeType(
                id=user.id,
                username=user.username,
                email=user.email,
                first_name=user.first_name,
                last_name=user.last_name,
                is_staff=user.is_staff,
                is_superuser=user.is_superuser,
            )
        raise Exception("Not authenticated")


schema = strawberry.Schema(query=Query)
