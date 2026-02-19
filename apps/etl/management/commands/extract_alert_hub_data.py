from django.core.management.base import BaseCommand

from apps.etl.etl_tasks.alert_hub import schedule_alert_hub_historical_extraction
from apps.etl.management.commands.utils import validate_date_format


class Command(BaseCommand):
    help = "Import data from EM-DAT"

    def confirm(self, message: str) -> bool:
        prompt = self.style.NOTICE(f"{message} (y/n): ")
        return input(prompt).strip().lower() == "y"

    def add_arguments(self, parser):
        parser.add_argument("--start-date", required=True, type=validate_date_format, help="Start date in YYYY-MM-DD format")
        parser.add_argument("--end-date", required=True, type=validate_date_format, help="End date in YYYY-MM-DD format")

    def handle(self, *args, **options):
        start_date = options["start_date"]
        end_date = options["end_date"]

        confirm_message = (
            f"Are you sure? This will trigger ALERTHUB import\nFROM:\t{start_date}\nTO:\t{end_date}\nPlease confirm"
        )
        if not self.confirm(confirm_message):
            self.stderr.write(self.style.ERROR("Skipped...."))
            return

        schedule_alert_hub_historical_extraction(start_date=start_date, end_date=end_date)

        self.stdout.write(self.style.SUCCESS("Triggered successfully"))
