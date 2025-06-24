<<<<<<< HEAD
=======
import logging
from datetime import datetime

>>>>>>> df01f39 (Get the start_date and end_date from the user for historical data pull; latest data pull from beginning of current month incase no data)
from django.core.management.base import BaseCommand, CommandParser

from apps.etl.etl_tasks.gdacs import ext_and_transform_gdacs_historical_data
from apps.etl.management.commands.utils import validate_dates

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Import data from gdacs api"

    def add_arguments(self, parser: CommandParser) -> None:
        """Set arguments"""
        parser.add_argument("start_date", type=str, help="Format: YYYY-MM-DD")
        parser.add_argument("end_date", type=str, help="Format: YYYY-MM-DD")

    def handle(self, *args, **options):
        """Handler"""
        start_date: str | None = options.get("start_date")
        end_date: str | None = options.get("end_date")

        dt_start_date, dt_end_date = validate_dates(start_date=start_date, end_date=end_date)

        if dt_start_date and dt_end_date:
            ext_and_transform_gdacs_historical_data(start_date=dt_start_date, end_date=dt_end_date)
