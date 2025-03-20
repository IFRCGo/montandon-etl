import logging
import os
from logging.config import dictConfig

from celery import Celery, signals

from utils.common import get_all_modules

from .cronjobs import BEAT_SCHEDULES

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "main.settings")

app = Celery("main")

app.config_from_object("django.conf:settings", namespace="CELERY")

# Default autodiscover (Looks at apps/*/tasks.py)
app.autodiscover_tasks()

# ETL tasks autodiscover
# NOTE: Hinting celery to look at additional files for tasks
app.autodiscover_tasks(get_all_modules("apps/etl/etl_tasks"))

app.conf.beat_schedule = BEAT_SCHEDULES

@signals.setup_logging.connect
def config_loggers(**_):
    from django.conf import settings

    dictConfig(settings.LOGGING)
