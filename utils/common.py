import copy
import datetime
import functools
import logging
import os
import re
import typing

from asgiref.sync import sync_to_async
from django.db import models
from django.shortcuts import get_object_or_404


def get_all_modules(dir: str) -> list[str]:
    """
    Get all modules within directory recursively.
    """
    modules = []
    for dirpath, _, filenames in os.walk(dir):
        for filename in filenames:
            # Get the full path of the file
            if not filename.endswith(".py"):
                continue
            file_path = os.path.join(dirpath, filename)
            file_path = file_path.replace(".py", "")
            file_path = file_path.replace("/", ".")
            modules.append(file_path)
    return modules


logger = logging.getLogger(__name__)


# Adapted from this response in Stackoverflow
# http://stackoverflow.com/a/19053800/1072990
def to_camel_case(snake_str):
    components = snake_str.split("_")
    # We capitalize the first letter of each component except the first one
    # with the 'capitalize' method and join them together.
    return components[0] + "".join(x.capitalize() if x else "_" for x in components[1:])


def to_snake_case(name):
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def get_queryset_for_model(
    model: typing.Type[models.Model],
    queryset: models.QuerySet | None = None,
) -> models.QuerySet:
    if queryset is not None:
        return copy.deepcopy(queryset)
    return model.objects.all()


def logger_log_extra(context_data):
    return {
        "context": context_data,
    }


@sync_to_async
def get_object_or_404_async(queryset, **kwargs):
    return get_object_or_404(queryset, **kwargs)


class RuntimeProfile:
    label: str
    start: typing.Optional[datetime.datetime]

    def __init__(self, label: str = "N/A"):
        self.label = label
        self.start = None

    def __call__(self, func):
        self.label = func.__name__

        @functools.wraps(func)
        def decorated(*args, **kwargs):
            with self:
                return func(*args, **kwargs)

        return decorated

    def __enter__(self):
        self.start = datetime.datetime.now()

    def __exit__(self, exc_type, exc_value, exc_traceback):
        assert self.start is not None
        time_delta = datetime.datetime.now() - self.start
        logger.info(f"Runtime with <{self.label}>: {time_delta}")
