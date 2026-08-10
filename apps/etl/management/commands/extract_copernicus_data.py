from django.core.management.base import BaseCommand

from apps.etl.etl_tasks.copernicus import ext_and_transform_copernicus_latest_data


class Command(BaseCommand):
    help = "Import data from copernicus api"

    def confirm(self, message: str) -> bool:
        prompt = self.style.NOTICE(f"{message} (y/n): ")
        return input(prompt).strip().lower() == "y"

    def handle(self, *args, **options):
        confirm_message = "Are you sure? This will trigger Copernicus import\nPlease confirm"
        if not self.confirm(confirm_message):
            self.stderr.write(self.style.ERROR("Skipped...."))
            return

        ext_and_transform_copernicus_latest_data()
        self.stdout.write(self.style.SUCCESS("Triggered successfully"))
