import strawberry
import strawberry_django

from apps.user.models import User


@strawberry_django.filters.filter(User, lookups=True)
class UserFilter:
    id: strawberry.auto
    display_name: strawberry.auto
