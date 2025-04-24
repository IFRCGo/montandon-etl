import strawberry
from typing import Optional
from utils.common import get_queryset_for_model
from django.db import models
import strawberry_django
from strawberry import auto
from main.graphql.context import Info
from apps.etl.enums import ExtractionSourceTypeEnum,PyStacLoadDataStatusEnum,PyStacLoadDataItemTypeEnum,ExtractionDataStatusTypeEnum

from apps.etl.models import ExtractionData,PyStacLoadData
from typing import List
@strawberry_django.type(ExtractionData)

class ExtractionDataType:
    id: auto
    source: ExtractionSourceTypeEnum
    status: ExtractionDataStatusTypeEnum
    url: auto
    resp_code: auto
    resp_data_type: auto
    parent_id: Optional[int]
    source_validation_status: auto
    hazard_type: auto
    trace_id: int

    def resolve_parent(self, root):
        return root.parent.id

    @staticmethod
    def get_queryset(_, queryset: models.QuerySet | None, info: Info):
        return get_queryset_for_model(ExtractionData, queryset)
    


@strawberry_django.type(PyStacLoadData)
class PyStacLoadDataType:
    id: auto
    status: PyStacLoadDataStatusEnum
    item_type: PyStacLoadDataItemTypeEnum
    collection_id:auto
    item:auto
    transform_id:int
    trace_id:int

    @staticmethod
    def get_queryset(_, queryset: models.QuerySet | None, info: Info):
        return get_queryset_for_model(PyStacLoadData, queryset)
    
@strawberry.type()
class EtlTraceGroup:
    trace_id: int
    extractions: List[ExtractionDataType]
    loads: List[PyStacLoadDataType]
