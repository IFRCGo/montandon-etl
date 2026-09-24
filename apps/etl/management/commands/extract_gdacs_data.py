from django.core.management.base import BaseCommand, CommandParser

from apps.etl.etl_tasks.gdacs import ext_and_transform_gdacs_historical_data
from apps.etl.management.commands.utils import validate_date_format


class Command(BaseCommand):
    help = "Import data from gdacs api"

    def confirm(self, message: str) -> bool:
        prompt = self.style.NOTICE(f"{message} (y/n): ")
        return input(prompt).strip().lower() == "y"

    def add_arguments(self, parser: CommandParser) -> None:
        """Set arguments"""
        parser.add_argument("--start-date", required=True, type=validate_date_format, help="Start date in YYYY-MM-DD format")
        parser.add_argument("--end-date", required=True, type=validate_date_format, help="End date in YYYY-MM-DD format")
        # NOTE: When --skip-detail-duplicates is set, events with an existing detail extraction are skipped.
        # This speeds up re-imports but means updates to previously extracted source data (e.g. a corrected
        # 2011 event) will NOT be captured. Omit this flag to force full re-extraction of all events.
        parser.add_argument(
            "--skip-detail-duplicates",
            action="store_true",
            default=False,
            help=(
                "Skip events whose detail extraction already exists. "
                "NOTE: If the source data for a previously extracted period has been updated, "
                "those changes will NOT be captured when this flag is set. "
                "Omit this flag to force re-extraction of all events."
            ),
        )

    def handle(self, *args, **options):
        """Handler"""
        start_date: str | None = options.get("start_date")
        end_date: str | None = options.get("end_date")
        skip_detail_duplicates: bool = options["skip_detail_duplicates"]

        note = (
            "\nNOTE: --skip-detail-duplicates is enabled. Already extracted events will be skipped. "
            "If source data has been updated for this period, those changes will NOT be captured. "
            "Re-run without this flag to force full re-extraction."
            if skip_detail_duplicates
            else ""
        )
        confirm_message = (
            f"Are you sure? This will trigger IFRC import\nFROM:\t{start_date}\nTO:\t{end_date}{note}\nPlease confirm"
        )
        if not self.confirm(confirm_message):
            self.stderr.write(self.style.ERROR("Skipped...."))
            return

        ext_and_transform_gdacs_historical_data(
            start_date=start_date, end_date=end_date, skip_detail_duplicates=skip_detail_duplicates
        )
        self.stdout.write(self.style.SUCCESS("Triggered successfully"))
