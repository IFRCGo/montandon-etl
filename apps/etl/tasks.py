from celery import shared_task
from django.core.management import call_command


@shared_task
def load_data():
    call_command("load_data_to_stac")
