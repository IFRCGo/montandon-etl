import strawberry
from asgiref.sync import sync_to_async

import strawberry_django
from typing import Optional
from main.graphql.context import Info
from utils.strawberry.paginations import CountList, pagination_field
from apps.etl.types import ExtractionDataType,PyStacLoadDataType,EtlTraceGroup
from apps.etl.filters import ExtractionDataFilter,PyStacLoadDataFilter
from apps.etl.models import ExtractionData,PyStacLoadData
@strawberry.type
class PublicQuery:
    extractions: CountList[ExtractionDataType] = pagination_field(
        pagination=True,
        filters=ExtractionDataFilter,
    )

    @strawberry_django.field()
    async def extraction(self, info: Info, pk: strawberry.ID) -> ExtractionDataType | None:
        return await ExtractionDataType.get_queryset(None, None, info).filter(pk=pk).afirst()

   
    pystacdatas: CountList[PyStacLoadDataType] = pagination_field(
        pagination=True,
        filters=PyStacLoadDataFilter,
    )
    @strawberry_django.field()
    async def pystacdata(self, info: Info, pk: strawberry.ID) -> PyStacLoadDataType | None:
        return await PyStacLoadDataType.get_queryset(None, None, info).filter(pk=pk).afirst()


    