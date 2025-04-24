import typing

from asgiref.sync import sync_to_async
from django.utils.functional import cached_property
from strawberry.dataloader import DataLoader

from django.db import models

from apps.etl.models import ExtractionData,PyStacLoadData




DjangoModel = typing.TypeVar("DjangoModel", bound=models.Model)


def load_model_objects(
    Model: typing.Type[DjangoModel],
    keys: list[int],
) -> list[DjangoModel]:
    qs = Model.objects.filter(id__in=keys)
    _map = {obj.pk: obj for obj in qs}
    return [_map[key] for key in keys]



if typing.TYPE_CHECKING:
    from apps.etl.types import ExtractionDataType,PyStacLoadDataType


def load_extraction(keys: list[int]) -> list["ExtractionDataType"]:
    return load_model_objects(ExtractionData, keys)  # type: ignore[reportReturnType]

def load_pystac(keys: list[int]) -> list["PyStacLoadDataType"]:
    return load_model_objects(PyStacLoadData, keys)  # type: ignore[reportReturnType]

class ExtractionDataLoader:
    @cached_property
    def load_data(self):
        return DataLoader(load_fn=sync_to_async(load_extraction))
    

class PystacDataLoader:
    @cached_property
    def load_data(self):
        return DataLoader(load_fn=sync_to_async(load_pystac))