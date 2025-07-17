import logging

from django.core.management.base import BaseCommand

from apps.etl.etl_tasks.desinventar import ext_and_transform_desinventar_historical_data

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Import data from desinventar"

    def confirm(self, message: str) -> bool:
        prompt = self.style.NOTICE(f"{message} (y/n): ")
        return input(prompt).strip().lower() == "y"

    def add_arguments(self, parser):
        parser.add_argument("--queue", required=True)
        parser.add_argument("--country_code", required=True, help="if multiple make sure to pass comma separated")

    def handle(self, *args, **options):
        queue = options["queue"]
        country_code = options["country_code"]

        confirm_message = (
            "Are you sure? This will trigger Desinventar import\n"
            f"Country code:\t{country_code}\n"
            f"QUEUE:\t{queue} (Make sure this exists)\n"
            "Please confirm"
        )
        if not self.confirm(confirm_message):
            self.stderr.write(self.style.ERROR("Skipped...."))
            return

        ext_and_transform_desinventar_historical_data(country_code_list=[country_code], queue_name=queue)
        self.stdout.write(self.style.SUCCESS("Triggered successfully"))
