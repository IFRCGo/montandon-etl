import strawberry
import strawberry_django
from typing import Optional
from utils.strawberry.enums import enum_field
from apps.etl.models import PyStacLoadData,ExtractionData
from apps.etl.enums import PyStacLoadDataItemTypeEnum,PyStacLoadDataStatusEnum,ExtractionDataStatusTypeEnum,ExtractionSourceTypeEnum

@strawberry_django.filters.filter(PyStacLoadData, lookups=True)
class PyStacLoadDataFilter:
    id: strawberry.auto
    status:PyStacLoadDataStatusEnum
    item_type:PyStacLoadDataItemTypeEnum
    trace_id:int

    

@strawberry_django.filters.filter(ExtractionData, lookups=True)
class ExtractionDataFilter:
    created_at: strawberry.auto
    source: ExtractionSourceTypeEnum
    status: ExtractionDataStatusTypeEnum

