import logging

from django.core.management.base import BaseCommand

from apps.etl.load.sources.gdacs import load_gdacs_data
from apps.etl.load.sources.glide import load_glide_data

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Import data from glide api"

    def handle(self, *args, **options):
        load_gdacs_data()
        load_glide_data()
