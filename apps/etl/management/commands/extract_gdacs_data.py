import logging
from datetime import datetime

from django.core.management.base import BaseCommand, CommandParser

from apps.etl.etl_tasks.gdacs import ext_and_transform_gdacs_historical_data

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Import data from gdacs api"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("start_date", type=str, help="Format: YYYY-MM-DD")
        parser.add_argument("end_date", type=str, help="Format: YYYY-MM-DD")

    def handle(self, *args, **options):
        start_date: str = options.get("start-date")
        end_date: str = options.get("end-date")

        try:
            if start_date and end_date:
                dt_start_date = datetime.strptime(start_date, "%Y-%m-%d")
                dt_end_date = datetime.strptime(end_date, "%Y-%m-%d")
                if dt_start_date > dt_end_date:
                    logger.error("Start date cannot be at a later date with respect to End date")
                    return
            else:
                logger.error("Start date or End date is not specified correctly")
                return
        except Exception:
            logger.error("Error occurred while processing the Start/End dates")
            return
        ext_and_transform_gdacs_historical_data(start_date=dt_start_date, end_date=dt_end_date)
