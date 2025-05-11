import strawberry
import strawberry_django

from apps.user.models import User


@strawberry_django.ordering.order(User)
class UserOrder:
    id: strawberry.auto
    display_name: strawberry.auto
