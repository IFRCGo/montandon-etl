import strawberry
import strawberry_django

from .types import UserMeType


@strawberry.type
class Mutation:
    # Public --------------------
    login: UserMeType = strawberry_django.auth.login()  # type: ignore[reportAssignmentType]

    # Private --------------------
    logout = strawberry_django.auth.logout()
