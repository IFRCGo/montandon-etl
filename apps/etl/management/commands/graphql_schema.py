import argparse

from django.core.management.base import BaseCommand
from strawberry.printer import print_schema

from main.graphql.schema import schema


class Command(BaseCommand):
    help = "Create schema.graphql file"

    def add_arguments(self, parser):
        parser.add_argument(
            "--out",
            type=argparse.FileType("w"),
            default="schema.graphql",
        )

    def handle(self, *args, **options):
        file = options["out"]
        # Trailing newline: print_schema omits it, but end-of-file-fixer adds one to the
        # committed schema, which would make the CI schema comparison always differ.
        file.write(print_schema(schema) + "\n")
        file.close()
        self.stdout.write(self.style.SUCCESS(f"{file.name} file generated"))
