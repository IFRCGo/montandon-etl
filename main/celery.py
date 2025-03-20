import os

from celery import Celery

from utils.common import get_all_modules

from .cronjobs import SCHEDULES

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "main.settings")

app = Celery("main")

app.config_from_object("django.conf:settings", namespace="CELERY")

# Default autodiscover (Looks at apps/*/tasks.py)
app.autodiscover_tasks()

# ETL tasks autodiscover
# NOTE: Hinting celery to look at additional files for tasks
app.autodiscover_tasks(get_all_modules("apps/etl/etl_tasks"))

app.conf.beat_schedule = SCHEDULES
