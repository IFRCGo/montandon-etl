import logging

from django.core.management.base import BaseCommand

from apps.etl.etl_tasks.desinventar import ext_and_transform_desinventar_historical_data

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Import data from desinventar"

    def confirm(self, message: str) -> bool:
        prompt = self.style.NOTICE(f"{message} (y/n): ")
        return input(prompt).strip().lower() == "y"

    def handle(self, *args, **options):
        confirm_message = "Are you sure? This will trigger Desinventar import. Please confirm"
        if not self.confirm(confirm_message):
            self.stderr.write(self.style.ERROR("Skipped...."))
            return

        ext_and_transform_desinventar_historical_data()
        self.stdout.write(self.style.SUCCESS("Triggered successfully"))
