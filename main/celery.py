import logging
import os
from logging.config import dictConfig

from celery import Celery, signals
from django.db import models

from utils.common import get_all_modules

from .cronjobs import BEAT_SCHEDULES

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "main.settings")

app = Celery("main")

app.config_from_object("django.conf:settings", namespace="CELERY")

# Default autodiscover (Looks at apps/*/tasks.py)
app.autodiscover_tasks()
app.conf.task_queues = {
    "default": {
        "exchange": "default",
        "routing_key": "default",
    },
    "extraction": {
        "exchange": "extraction",
        "routing_key": "extraction",
    },
    "transform": {
        "exchange": "transform",
        "routing_key": "transform",
    },
}

app.conf.task_default_queue = "default"

# ETL tasks autodiscover
# NOTE: Hinting celery to look at additional files for tasks
app.autodiscover_tasks(get_all_modules("apps/etl/etl_tasks"))

app.conf.beat_schedule = BEAT_SCHEDULES

logger = logging.getLogger(__name__)


@signals.beat_init.connect
def clean_up_periodic_tasks(**_):
    try:
        from django_celery_beat.models import PeriodicTask

        obsolute_tasks_qs = PeriodicTask.objects.filter(
            task__startswith="apps.",  # Our tasks
        ).exclude(
            models.Q(
                name__in=list(BEAT_SCHEDULES.keys()),
            )
            | models.Q(
                name__startswith="manual:",  # Lets filter-out if it has `manual:` at the start
            )
        )

        obsolute_tasks = list(obsolute_tasks_qs)
        if obsolute_tasks:
            for task in obsolute_tasks:
                logger.warning(f"Task to delete: {task.name}")

            deleted_periodic_task = obsolute_tasks_qs.delete()
            logger.warning(f"Deleted tasks not defined in the codebase: {deleted_periodic_task}")
    except Exception:
        logger.error("Failed to clean-up PeriodicTasks", exc_info=True)


@signals.setup_logging.connect
def config_loggers(**_):
    from django.conf import settings

    dictConfig(settings.LOGGING)
