from django.core.management.base import BaseCommand

from apps.etl.etl_tasks.gdacs import ext_and_transform_gdacs_historical_data


class Command(BaseCommand):
    help = "Import data from gdacs api"

    def handle(self, *args, **options):
        ext_and_transform_gdacs_historical_data()
