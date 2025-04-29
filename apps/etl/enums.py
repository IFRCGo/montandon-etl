import strawberry

from apps.etl.models import ExtractionData, PyStacLoadData, Status
from utils.strawberry.enums import get_enum_name_from_django_field

ExtractionDataStatusTypeEnum = strawberry.enum(Status, name="ExtractionDataStatusTypeEnum")
ExtractionValidationTypeEnum = strawberry.enum(
    ExtractionData.ValidationStatus, name="ExtractionDataValidationStatusTypeEnum"
)
ExtractionSourceTypeEnum = strawberry.enum(ExtractionData.Source, name="ExtractionSourceTypeEnum")

PyStacLoadDataStatusEnum = strawberry.enum(PyStacLoadData.Status, name="PyStacLoadDataStatusEnum")
PyStacLoadDataItemTypeEnum = strawberry.enum(PyStacLoadData.ItemType, name="PyStacLoadDataItemTypeEnum")


enum_map = {
    get_enum_name_from_django_field(field): enum
    for field, enum in (
        (ExtractionData.source, ExtractionSourceTypeEnum),
        (ExtractionData.status, ExtractionDataStatusTypeEnum),
        (ExtractionData.source_validation_status, ExtractionValidationTypeEnum),
        (PyStacLoadData.status, PyStacLoadDataStatusEnum),
        (PyStacLoadData.item_type, PyStacLoadDataItemTypeEnum),
    )
}
