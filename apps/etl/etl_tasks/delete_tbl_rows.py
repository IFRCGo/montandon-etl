from celery import shared_task
from django.core.management import call_command


@shared_task
def cleanup_pystac_load_data():
    call_command("cleanup_pystac_load_data_success_rows", batch_size=5000)
