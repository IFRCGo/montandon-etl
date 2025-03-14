from celery import shared_task
from django.core.management import call_command


@shared_task
def extract_pdc_data():
    call_command("extract_pdc_data")


@shared_task
def extract_gidd_data():
    call_command("extract_gidd_data")


@shared_task
def extract_usgs_data():
    call_command("extract_usgs_data")


@shared_task
def load_data():
    call_command("load_data_to_stac")