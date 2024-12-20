from typing import Optional

import strawberry
from strawberry import auto
from django.contrib.auth.models import User


@strawberry.django.type(User)
class UserMeType:
    id: auto
    username: auto
    first_name: auto
    last_name: auto
    email: auto
    is_staff: auto
    is_superuser: auto

