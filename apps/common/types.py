import strawberry_django
from django.contrib.auth.models import User
from strawberry import auto


@strawberry_django.type(User)
class UserMeType:
    id: auto
    username: auto
    first_name: auto
    last_name: auto
    email: auto
    is_staff: auto
    is_superuser: auto
