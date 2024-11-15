from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = "Import data from gdacs api"

    def handle(self, *args, **options):
        print("Importing data from GDACS api")
