
import typing

from asgiref.sync import sync_to_async
from django.utils.functional import cached_property
from strawberry.dataloader import DataLoader

from common.dataloaders import load_model_objects

from .models import User

if typing.TYPE_CHECKING:
    from .types import ExtractionDataType


def load_extraction(keys: list[int]) -> list["ExtractionDataType"]:
    return load_model_objects(User, keys)  # type: ignore[reportReturnType]


class ExtractionDataLoader:
    @cached_property
    def load_extraction(self):
        return DataLoader(load_fn=sync_to_async(load_extraction))
