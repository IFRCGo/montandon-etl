import strawberry
import strawberry_django

from apps.etl.models import ExtractionData, PyStacLoadData, Transform


@strawberry_django.ordering.order(ExtractionData)
class ExtractionOrder:
    id: strawberry.auto
    source: strawberry.auto
    trace_id: strawberry.auto
    source_validation_status: strawberry.auto
    status: strawberry.auto
    hazard_type: strawberry.auto


@strawberry_django.ordering.order(Transform)
class TransformOrder:
    id: strawberry.auto
    source: strawberry.auto = strawberry.field(name="extraction__source")
    extraction__trace_id: strawberry.auto
    extraction__source_validation_status: strawberry.auto
    extraction__status: strawberry.auto
    extraction__hazard_type: strawberry.auto


@strawberry_django.ordering.order(PyStacLoadData)
class PystacOrder:
    id: strawberry.auto
