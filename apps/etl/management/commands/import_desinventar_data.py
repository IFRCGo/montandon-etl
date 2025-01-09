import logging

from django.core.management.base import BaseCommand

from apps.etl.desinventar.task import import_desinventar_data
from apps.etl.models import HazardType

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Import data from desinventar"

    def handle(self, *args, **options):
        import_desinventar_data()
