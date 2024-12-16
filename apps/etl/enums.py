import strawberry
from .models import ExtractionData

ExtractionDataStatusTypeEnum = strawberry.enum(
    ExtractionData.Status, name="ExtractionDataStatusTypeEnum"
)
ExtractionValidationTypeEnum = strawberry.enum(
    ExtractionData.ValidationStatus, name="ExtractionDataValidationStatusTypeEnum"
)
ExtractionSourceTypeEnum = strawberry.enum(
    ExtractionData.Source, name="ExtractionDataSourceTypeEnum"
)
