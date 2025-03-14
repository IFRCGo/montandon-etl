from django.core.management.base import BaseCommand

from apps.etl.etl_tasks.glide import ext_and_transform_glide_historical_data


class Command(BaseCommand):
    help = "Import data from glide api"

    def handle(self, *args, **options):
        ext_and_transform_glide_historical_data()
