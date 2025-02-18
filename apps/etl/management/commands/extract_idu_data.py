from django.core.management.base import BaseCommand

from apps.etl.etl_tasks.idu import ext_and_transform_idu_historical_data


class Command(BaseCommand):
    help = "Import data from IDU"

    def handle(self, *args, **options):
        ext_and_transform_idu_historical_data()
