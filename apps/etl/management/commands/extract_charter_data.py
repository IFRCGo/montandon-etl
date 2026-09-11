from django.core.management.base import BaseCommand, CommandParser

from apps.etl.etl_tasks.charter import (
    ext_and_transform_charter_data_for_activations,
    ext_and_transform_charter_latest_data,
)


class Command(BaseCommand):
    help = "Import data from Disaster Charter"

    def confirm(self, message: str) -> bool:
        prompt = self.style.NOTICE(f"{message} (y/n): ")
        return input(prompt).strip().lower() == "y"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--activation-ids",
            nargs="+",
            type=int,
            help="One or more activation IDs to extract. If omitted, extracts the full catalog.",
        )

    def handle(self, *_args, **options):
        activation_ids: list[int] | None = options.get("activation_ids")

        if activation_ids:
            confirm_message = (
                f"Are you sure? This will trigger Disaster Charter import"
                f" for activation IDs: {activation_ids}\nPlease confirm"
            )
        else:
            confirm_message = "Are you sure? This will trigger Disaster Charter import for the full catalog.\nPlease confirm"

        if not self.confirm(confirm_message):
            self.stderr.write(self.style.ERROR("Skipped...."))
            return

        if activation_ids:
            ext_and_transform_charter_data_for_activations(activation_ids=activation_ids)
        else:
            ext_and_transform_charter_latest_data()

        self.stdout.write(self.style.SUCCESS("Triggered successfully"))
