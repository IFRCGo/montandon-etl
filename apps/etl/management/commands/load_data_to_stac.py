import logging

from django.core.management.base import BaseCommand

from apps.etl.load.sources.base import load_data

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Load data to stac api"

    def handle(self, *args, **options):
        load_data(django_command=self)
