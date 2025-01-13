from typing import Optional

import strawberry_django
from strawberry import auto

from .enums import ExtractionDataStatusTypeEnum, ExtractionSourceTypeEnum
from .models import ExtractionData


@strawberry_django.type(ExtractionData)
class ExtractionDataType:
    id: auto
    source: ExtractionSourceTypeEnum
    url: auto
    resp_code: auto
    status: ExtractionDataStatusTypeEnum
    resp_data_type: auto
    parent_id: Optional[int]
    source_validation_status: auto
    revision_id: Optional[int]
    hazard_type: auto

    def resolve_parent(self, root):
        return root.parent.id

    def resolve_revision_id(self, root):
        return root.revision_id.id
