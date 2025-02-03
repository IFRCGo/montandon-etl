import logging

from django.core.management.base import BaseCommand

from apps.etl.etl_tasks.gidd import ext_and_transform_gidd_latest_data

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Import data from glide api"

    def handle(self, *args, **options):
        ext_and_transform_gidd_latest_data()
