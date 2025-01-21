import logging

from django.core.management.base import BaseCommand

from apps.etl.etl_tasks.emdat import import_emdat_hazard_data

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Import data from EM-DAT"

    def handle(self, *args, **options):
        import_emdat_hazard_data()
