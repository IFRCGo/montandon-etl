import strawberry


from apps.etl.types import (
    ExtractionDataType,
    ExtractionDataListType,
)


@strawberry.type
class Query():
    extraction_data_list: list[ExtractionDataListType] = strawberry.django.field()
    extraction_data: ExtractionDataType = strawberry.django.field()


schema = strawberry.Schema(query=Query)