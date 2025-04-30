import strawberry

from apps.etl.models import ExtractionData, PyStacLoadData, Status
from utils.strawberry.enums import get_enum_name_from_django_field

DataStatusTypeEnum = strawberry.enum(Status, name="DataStatusTypeEnum")
ExtractionValidationTypeEnum = strawberry.enum(
    ExtractionData.ValidationStatus, name="ExtractionDataValidationStatusTypeEnum"
)
SourceTypeEnum = strawberry.enum(ExtractionData.Source, name="SourceTypeEnum")
PyStacLoadDataStatusEnum = strawberry.enum(PyStacLoadData.Status, name="PyStacLoadDataStatusEnum")
PyStacLoadDataItemTypeEnum = strawberry.enum(PyStacLoadData.ItemType, name="PyStacLoadDataItemTypeEnum")


enum_map = {
    get_enum_name_from_django_field(field): enum
    for field, enum in (
        (ExtractionData.source, SourceTypeEnum),
        (ExtractionData.status, DataStatusTypeEnum),
        (ExtractionData.source_validation_status, ExtractionValidationTypeEnum),
        (PyStacLoadData.status, PyStacLoadDataStatusEnum),
        (PyStacLoadData.item_type, PyStacLoadDataItemTypeEnum),
    )
}
