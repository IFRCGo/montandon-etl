import strawberry
from strawberry import auto
import strawberry_django

from .models import (
    ExtractionData,
)


@strawberry_django.ordering.order(ExtractionData)
class ExtractionDataOrderType:
    order: auto


@strawberry.django.type(ExtractionData)
class ExtractionDataType:
    id: auto
    order: auto


@strawberry.django.type(ExtractionData, pagination=True, filters=None)
class ExtractionDataListType(ExtractionData):
    pass
