import logging

from django.core.management.base import BaseCommand

from apps.etl.etl_tasks.pdc import extract_and_transform_historical_pdc_data
from apps.etl.management.commands.extract_usgs_data import validate_date_format

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Import data from pdc api"

    def confirm(self, message: str) -> bool:
        prompt = self.style.NOTICE(f"{message} (y/n): ")
        return input(prompt).strip().lower() == "y"

    def add_arguments(self, parser):
        parser.add_argument("--queue", required=True)
        parser.add_argument("--start-date", required=True, type=validate_date_format, help="Start date in YYYY-MM-DD format")
        parser.add_argument("--end-date", required=True, type=validate_date_format, help="End date in YYYY-MM-DD format")

    def handle(self, *args, **options):
        queue = options["queue"]
        start_date = options["start_date"]
        end_date = options["end_date"]

        confirm_message = (
            "Are you sure? This will trigger PDC import\n"
            f"FROM:\t{start_date}\n"
            f"TO:\t{end_date}\n"
            f"QUEUE:\t{queue} (Make sure this exists)\n"
            "Please confirm"
        )
        if not self.confirm(confirm_message):
            self.stderr.write(self.style.ERROR("Skipped...."))
            return

        extract_and_transform_historical_pdc_data(start_date=start_date, end_date=end_date, queue_name=queue)
        self.stdout.write(self.style.SUCCESS("Triggered successfully"))
