import logging

from django.core.management.base import BaseCommand

from apps.etl.etl_tasks.desinventar import import_desinventar_data

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Import data from desinventar"

    def handle(self, *args, **options):
        import_desinventar_data()
