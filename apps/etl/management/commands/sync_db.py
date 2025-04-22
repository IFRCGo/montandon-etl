import logging

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.etl.models import PyStacLoadData
from apps.etl.utils import generate_item_index_fields_values
from main.managers import BulkUpdateManager

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = " Extract key value pairs"

    @transaction.atomic
    def handle(self, *args, **options):
        pystac_objects = PyStacLoadData.objects.filter(item_id=None)
        bulk_mgr = BulkUpdateManager(chunk_size=1000, update_fields=["item_id", "item_datetime", "item_primary_country"])

        for component in pystac_objects.iterator():
            data = component.item or {}
            item_id, item_datetime, item_primary_country = generate_item_index_fields_values(data)
            bulk_mgr.add(
                PyStacLoadData(
                    id=component.id, item_id=item_id, item_datetime=item_datetime, item_primary_country=item_primary_country
                )
            )

        bulk_mgr.done()
        logging.info(bulk_mgr.summary())
