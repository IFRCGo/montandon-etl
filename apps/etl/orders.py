import strawberry
import strawberry_django

from apps.etl.models import ExtractionData, PyStacLoadData, Transform


@strawberry_django.ordering.order(ExtractionData)
class ExtractionOrder:
    id: strawberry.auto


@strawberry_django.ordering.order(Transform)
class TransformOrder:
    id: strawberry.auto


@strawberry_django.ordering.order(PyStacLoadData)
class PystacOrder:
    id: strawberry.auto
