from enum import Enum

import sentry_sdk
from billiard.exceptions import Terminated
from celery import signals
from celery.exceptions import Retry as CeleryRetry
from django.conf import settings
from django.core.exceptions import PermissionDenied
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.logging import ignore_logger
from sentry_sdk.integrations.redis import RedisIntegration

IGNORED_ERRORS = [
    Terminated,
    PermissionDenied,
    CeleryRetry,
]
IGNORED_LOGGERS = [
    "graphql.execution.utils",
    "strawberry.http.exceptions.HTTPException",
]

for _logger in IGNORED_LOGGERS:
    ignore_logger(_logger)


@signals.beat_init.connect
@signals.celeryd_init.connect
def init_sentry(**_):
    if not settings.SENTRY_ENABLED:
        return

    integrations = [
        DjangoIntegration(),
        RedisIntegration(),
        CeleryIntegration(monitor_beat_tasks=settings.SENTRY_MONITOR_CELERY_BEAT_TASKS),
    ]
    sentry_sdk.init(
        settings.SENTRY_CONFIG,
        ignore_errors=IGNORED_ERRORS,
        integrations=integrations,
    )
    app_type = settings.SENTRY_ADDITIONAL_CONFIG["app_type"]
    tags = settings.SENTRY_ADDITIONAL_CONFIG["tags"]
    with sentry_sdk.configure_scope() as scope:
        scope.set_tag("app_type", app_type)
        for tag, value in tags.items():
            scope.set_tag(tag, value)


class SentryTag:
    class Tag(str, Enum):
        _BASE = "MONTY-ETL."
        SOURCE = _BASE + "SOURCE"
        TRACE_ID = _BASE + "TRACE_ID"

    @staticmethod
    def set_tags(kwargs: dict[Tag, int | str]):
        if not settings.SENTRY_ENABLED:
            return
        for key, value in kwargs.items():
            sentry_sdk.set_tag(key.value, value)
