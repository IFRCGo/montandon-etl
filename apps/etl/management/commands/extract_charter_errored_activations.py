from django.core.management.base import BaseCommand

from apps.etl.extraction.sources.charter.extract import (
    ERRORED_ACTIVATION_IDS,
    CharterExtraction,
    CharterExtractionMetadata,
    CharterExtractionMetadataType,
)
from main.celery import CeleryQueue
from main.configs import etl_config


class Command(BaseCommand):
    help = "Run ETL for Disaster Charter activations that are excluded from normal ETL runs"

    def confirm(self, message: str) -> bool:
        prompt = self.style.NOTICE(f"{message} (y/n): ")
        return input(prompt).strip().lower() == "y"

    def handle(self, *_args, **_options):
        activation_ids = sorted(ERRORED_ACTIVATION_IDS)
        confirm_message = (
            f"Are you sure? This will trigger Disaster Charter import for"
            f" {len(activation_ids)} errored activation IDs: {activation_ids}\nPlease confirm"
        )

        if not self.confirm(confirm_message):
            self.stderr.write(self.style.ERROR("Skipped...."))
            return

        for activation_id in activation_ids:
            activation_url = (
                f"s3://{etl_config.CHARTER_S3_BUCKET_NAME}/activations/act-{activation_id}/act-{activation_id}.json"
            )
            CharterExtraction.init_extraction(
                metadata=CharterExtractionMetadata(
                    url=activation_url,
                    type=CharterExtractionMetadataType.ACTIVATION,
                    activation_id=activation_id,
                ),
                queue_name=CeleryQueue.EXTRACTION,
            )

        self.stdout.write(self.style.SUCCESS(f"Triggered successfully for {len(activation_ids)} activation IDs"))
