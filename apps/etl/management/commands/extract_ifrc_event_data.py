from django.core.management.base import BaseCommand

from apps.etl.etl_tasks.ifrc_event import ext_and_transform_ifrcevent_historical_data


class Command(BaseCommand):
    help = "Import data from glide api"

    def handle(self, *args, **options):
        ext_and_transform_ifrcevent_historical_data()
