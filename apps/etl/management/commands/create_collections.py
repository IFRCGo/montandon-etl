import json
import logging

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandParser

from apps.etl.transform.sources.handler import ITEM_TYPE_COLLECTION_ID_MAP

logger = logging.getLogger(__name__)

REQ_TIMEOUT = 30  # in seconds


class Command(BaseCommand):
    """Command to create collections in eoAPI server"""

    help = "Create collections in eoAPI server"

    def confirm(self, message: str) -> bool:
        """Confirmation message"""
        prompt = self.style.WARNING(f"{message} (y/n): ")
        return input(prompt).strip().lower() == "y"

    def add_arguments(self, parser: CommandParser) -> None:
        """Set arguments"""
        parser.add_argument("--eoapi-url", required=False, help="eoAPI server url")
        parser.add_argument("--token", required=False, help="eoAPI token")
        parser.add_argument(
            "--dry-run", action="store_true", default=False, help="Only show steps, don't send real requests"
        )

    def get_existing_collections(self, eoapi_url: str, headers: dict) -> None:
        """Returns the existing collections in remote eoAPI server"""
        response = requests.get(url=f"{eoapi_url}/collections?limit=50", headers=headers, timeout=REQ_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        collections_lst = [item["id"] for item in data["collections"]]

        self.stdout.write("Existing Collections:")
        for collection in collections_lst:
            self.stdout.write(f"- {collection}")

    def handle(self, *args, **options):
        """Handler"""
        dry_run: bool = options["dry_run"]
        eoapi_url: str | None = options.get("eoapi_url")
        eoapi_token: str | None = options.get("token")
        if not eoapi_url:
            eoapi_url = settings.EOAPI_STAC_API_INTERNAL
            if not eoapi_url:
                self.stderr.write(self.style.ERROR("eoAPI url not found in the environment. Exiting."))
                return
            self.stdout.write(self.style.WARNING(f"Using the eoAPI url from the environment: {eoapi_url}"))

        if not eoapi_token:
            self.stderr.write(self.style.WARNING("eoAPI token not provided. This might not work."))

        if dry_run:
            self.stdout.write(self.style.WARNING("Running in dry mode"))

        self.stdout.write(f"Using the eoAPI url: {eoapi_url}")

        headers = {"Authorization": f"Bearer {eoapi_token}", "Content-Type": "application/json"}
        # List all existing collections
        self.get_existing_collections(eoapi_url=eoapi_url, headers=headers)

        confirm_message = f"Are you sure you want to create collections in {eoapi_url}?"
        if not self.confirm(confirm_message):
            self.stderr.write(self.style.ERROR("Operation canceled... Exiting...."))
            return

        for key in ITEM_TYPE_COLLECTION_ID_MAP:
            self.stdout.write(f"------------------- Processing {key}")

            collection_file = settings.BASE_DIR / f"libs/pystac-monty/monty-stac-extension/examples/{key}/{key}.json"
            self.stdout.write(f"Using {collection_file}")

            with collection_file.open("r", encoding="utf-8") as fp:
                metadata = json.load(fp)

            assert metadata["id"] == key

            collection_payload = {
                **metadata,
                "id": key,
            }

            if dry_run:
                self.stdout.write("[Dry run]: Using this config")
                self.stdout.write(json.dumps(collection_payload, indent=2))
                continue

            response = requests.post(
                url=f"{eoapi_url}/collections",
                headers=headers,
                json=collection_payload,
                timeout=REQ_TIMEOUT,
            )
            if response.status_code in [200, 201]:
                self.stdout.write(self.style.SUCCESS(f"For collection: {metadata['id']}, the response is {response}"))
            else:
                self.stderr.write(self.style.ERROR(f"For collection: {metadata['id']}, the response is {response}"))
        self.stdout.write(self.style.SUCCESS("Task is complete."))
