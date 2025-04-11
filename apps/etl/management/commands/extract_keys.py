import logging

from django.core.management.base import BaseCommand

from apps.etl.models import PyStacLoadData

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Import data from gdacs api"

    def handle(self, *args, **options):
        components = PyStacLoadData.objects.all()

        updated = 0
        for component in components:
            data = component.item or {}

            id = data.get("id")
            idatetime = data.get("datetime")

            if id:
                component.item_id = id
            if idatetime:
                component.item_datetime = idatetime

            if id or idatetime:
                component.save()
                updated += 1

        self.stdout.write(self.style.SUCCESS(f"Updated {updated} records."))
