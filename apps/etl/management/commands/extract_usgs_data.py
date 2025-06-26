import argparse
import datetime
import logging

from django.core.management.base import BaseCommand

from apps.etl.etl_tasks.usgs import ext_and_transform_usgs_historical_data

logger = logging.getLogger(__name__)


# FIXME: Move this to utils? Add expected format using partial function
def validate_date_format(value) -> datetime.date:
    try:
        # Try parsing the date using the given format
        return datetime.datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid date format: '{value}'. Expected format: YYYY-MM-DD.")


class Command(BaseCommand):
    help = "Import data from usgs"

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
            "Are you sure? This will trigger USGS import\n"
            f"FROM:\t{start_date}\n"
            f"TO:\t{end_date}\n"
            f"QUEUE:\t{queue} (Make sure this exists)\n"
            "Please confirm"
        )
        if not self.confirm(confirm_message):
            self.stderr.write(self.style.ERROR("Skipped...."))
            return

        ext_and_transform_usgs_historical_data(start_date=start_date, end_date=end_date, queue_name=queue)
        self.stdout.write(self.style.SUCCESS("Triggered successfully"))
