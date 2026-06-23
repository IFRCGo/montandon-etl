import time
from argparse import ArgumentTypeError
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandParser
from django.db import connection
from django.utils import timezone

from apps.etl.models import ExtractionData, PyStacLoadData


class Command(BaseCommand):
    help = "Delete successful rows in batches with VACUUM"

    def positive_int(self, value: str) -> int:
        try:
            ivalue = int(value)
        except ValueError:
            raise ArgumentTypeError(f"{value} is not a valid integer")

        if ivalue <= 0:
            raise ArgumentTypeError("Value must be greater than 0")
        return ivalue

    def add_arguments(self, parser: CommandParser):
        parser.add_argument("--batch-size", type=self.positive_int, default=5000, help="Number of rows to delete at once")
        parser.add_argument("--retention-days", type=self.positive_int, default=30, help="In days")
        parser.add_argument("--max-rows", type=self.positive_int, default=100_000, help="Total number of rows to delete")

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        max_rows = options["max_rows"]
        retention_days = options["retention_days"]

        total_deleted = 0

        TABLE_NAME = PyStacLoadData._meta.db_table

        cutoff = timezone.now() - timedelta(days=retention_days)

        while True:
            remaining_rows = max_rows - total_deleted
            current_batch_size = min(batch_size, remaining_rows)

            query_set = PyStacLoadData.objects.filter(
                status=ExtractionData.Status.SUCCESS,
                item_datetime__lt=cutoff,
            ).order_by("id")

            ids = list(query_set.values_list("id", flat=True)[:current_batch_size])

            if not ids:
                break

            # NOTE PyStacLoadData has no related objects with cascading deletes,
            # so the count returned by delete() is exactly the number of
            # PyStacLoadData rows deleted.
            deleted_count, _ = query_set.filter(id__in=ids).delete()

            total_deleted += deleted_count

            if total_deleted >= max_rows:
                break

            time.sleep(0.2)  # Sleep between deletion process

        if total_deleted:
            self.stdout.write("Running VACUUM Analyze..")
            old_autocommit = connection.get_autocommit()
            try:
                connection.set_autocommit(True)
                with connection.cursor() as cursor:
                    cursor.execute(f"VACUUM ANALYZE {TABLE_NAME};")
            finally:
                connection.set_autocommit(old_autocommit)

        self.stdout.write(f"Total deleted: {total_deleted}")
