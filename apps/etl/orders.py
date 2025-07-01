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
    extraction__source: strawberry.auto = strawberry.field(name="source", default=strawberry.UNSET)
    extraction__trace_id: strawberry.auto = strawberry.field(name="traceId", default=strawberry.UNSET)
    extraction__source_validation_status: strawberry.auto = strawberry.field(
        name="validation_status", default=strawberry.UNSET
    )
    extraction__status: strawberry.auto = strawberry.field(name="status", default=strawberry.UNSET)
    extraction__hazard_type: strawberry.auto = strawberry.field(name="hazardType", default=strawberry.UNSET)


@strawberry_django.ordering.order(PyStacLoadData)
class PystacOrder:
    id: strawberry.auto
    transform_id__extraction__source: strawberry.auto = strawberry.field(name="source", default=strawberry.UNSET)
    transform_id__extraction__trace_id: strawberry.auto = strawberry.field(name="traceId", default=strawberry.UNSET)
    transform_id__extraction__source_validation_status: strawberry.auto = strawberry.field(
        name="validation_status", default=strawberry.UNSET
    )
    transform_id__extraction__status: strawberry.auto = strawberry.field(name="status", default=strawberry.UNSET)
    transform_id__extraction__hazard_type: strawberry.auto = strawberry.field(name="hazardType", default=strawberry.UNSET)
