import json
import logging
import re
import typing
import uuid
from enum import Enum
from functools import cached_property
from urllib.parse import urlparse

import boto3
import pydantic
import requests
from botocore.exceptions import BotoCoreError, ClientError
from celery import Task, chord
from pystac_monty.sources.charter import compute_file_hash

from apps.etl.extraction.sources.base.handler import BaseExtractionV2
from apps.etl.extraction.sources.base.utils import manage_duplicate_file_content
from apps.etl.models import ExtractionData
from apps.etl.transform.sources.charter import CharterTransformHandler
from main.celery import CeleryQueue, app
from main.configs import etl_config
from main.logging import log_extra
from utils.celery import RetryableTask

logger = logging.getLogger(__name__)


class CharterExtractionMetadataType(str, Enum):
    CATALOG = "CATALOG"
    ACTIVATION = "ACTIVATION"
    AREA = "AREA"
    VAPS_CATALOG = "VAPS_CATALOG"
    VAPS = "VAPS"
    CALIBRATED_DATASETS = "CALIBRATED_DATASETS"  # Legacy container type; kept for backward compat
    CALIBRATED_DATASET = "CALIBRATED_DATASET"


class CharterExtractionMetadata(pydantic.BaseModel):
    url: str
    type: CharterExtractionMetadataType
    activation_id: int | None = None
    area_id: str | None = None
    call_id: int | None = None
    s3_etag: str | None = None


class CharterExtraction(BaseExtractionV2[CharterExtractionMetadata]):
    """Extracts Disaster Charter data from S3 in a fan-out tree of Celery tasks.

    Extraction flow
    ---------------
    1. CATALOG — lists all activations under s3://.../activations/ and queues
       one ACTIVATION task per activation ID.

    2. ACTIVATION — fetches the activation JSON (act-{id}.json), then fans out
       three sets of child tasks in parallel:
         - AREA tasks    — one per area linked in the activation JSON
         - VAPS tasks    — one per VAP folder found under .../vaps/
         - CALIBRATED_DATASET tasks — one per calibrated dataset folder found under
                               .../calls/call-{id}/calibratedDatasets/

       All child tasks are grouped into a Celery chord so that the transform
       fires exactly once when every child completes.

    3. AREA / VAPS / CALIBRATED_DATASET — each fetches its own JSON file from S3
       and stores it. No further fan-out.

    Deduplication (two layers)
    --------------------------
    Before downloading a file, we check the S3 ETag (via HEAD). If a prior
    successful extraction exists with the same URL + ETag, we reuse it and
    skip the download entirely.

    If the ETag changed (file was touched on S3), we download and compute a
    *semantic hash* — the SHA-256 of the JSON with volatile administrative
    fields (``updated``, ``created``, ``cpe:notified``) stripped out. If the
    semantic hash matches a prior extraction, only timestamps changed and we
    skip the transform.
    """

    source_enum = ExtractionData.Source.DISASTERCHARTER
    extraction_metadata_class = CharterExtractionMetadata

    # ------------------------------------------------------------------ #
    # S3 helpers                                                           #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _s3_uri(*parts: str) -> str:
        return f"s3://{etl_config.CHARTER_S3_BUCKET_NAME}/{'/'.join(parts)}"

    @cached_property
    def _s3_client(self):
        return boto3.client(
            "s3",
            endpoint_url=etl_config.CHARTER_S3_ENDPOINT_URL,
            aws_access_key_id=etl_config.CHARTER_S3_ACCESS_KEY_ID,
            aws_secret_access_key=etl_config.CHARTER_S3_SECRET_ACCESS_KEY,
        )

    def _list_s3_prefixes(self, prefix: str) -> list[str]:
        """Return the last path component for each immediate sub-prefix under *prefix*.

        Raises BotoCoreError / ClientError on S3 failure — callers are responsible
        for catching and deciding whether to skip or abort.
        """
        paginator = self._s3_client.get_paginator("list_objects_v2")
        pages = paginator.paginate(
            Bucket=etl_config.CHARTER_S3_BUCKET_NAME,
            Prefix=prefix,
            Delimiter="/",
        )
        return [
            tail
            for page in pages
            for entry in page.get("CommonPrefixes", [])
            if (tail := entry.get("Prefix", "").rstrip("/").split("/")[-1])
        ]

    # ------------------------------------------------------------------ #
    # S3 fetch                                                             #
    # ------------------------------------------------------------------ #

    def _fetch_s3_file(self, s3_uri: str) -> bool:
        """Fetch one S3 object and store it.  Returns False if content is unchanged."""
        parsed = urlparse(s3_uri)
        bucket = parsed.netloc
        key = parsed.path.lstrip("/")

        etag = None
        try:
            head = self._s3_client.head_object(Bucket=bucket, Key=key)
            etag = head.get("ETag", "").strip('"') or None
        except (BotoCoreError, ClientError):
            logger.warning(
                "Failed to HEAD S3 object, skipping ETag dedup: %s",
                s3_uri,
                extra=log_extra({"source": self.source_enum}),
            )

        if etag:
            prev = (
                ExtractionData.objects.filter(
                    source=ExtractionData.Source.DISASTERCHARTER,
                    metadata__url=s3_uri,
                    metadata__s3_etag=etag,
                    status=ExtractionData.Status.SUCCESS,
                )
                .exclude(pk=self.extraction_object.pk)
                .first()
            )
            if prev is not None:
                self.extraction_object.resp_code = 200
                self.extraction_object.resp_data = prev.resp_data
                self.extraction_object.revision_id = prev
                self.extraction_object.file_hash = prev.file_hash
                self.extraction_object.source_validation_status = ExtractionData.ValidationStatus.NO_CHANGE
                self.extraction_object.metadata = {**self.extraction_object.metadata, "s3_etag": etag}
                self.extraction_object.save(
                    update_fields=[
                        "resp_code",
                        "resp_data",
                        "revision_id",
                        "file_hash",
                        "source_validation_status",
                        "metadata",
                    ]
                )
                logger.info("S3 content unchanged (ETag match), skipping fetch: %s", s3_uri)
                return False

        try:
            s3_response = self._s3_client.get_object(Bucket=bucket, Key=key)
            content = s3_response["Body"].read()
        except (ClientError, BotoCoreError) as exc:
            logger.error(
                "Failed to fetch from S3: %s",
                s3_uri,
                extra=log_extra({"source": self.source_enum}),
                exc_info=True,
            )
            raise requests.exceptions.ConnectionError(str(exc)) from exc

        if not content:
            raise requests.exceptions.ConnectionError(f"Empty content returned from S3: {s3_uri}")

        self.extraction_object.resp_code = 200
        self.extraction_object.resp_data_type = "application/geo+json"
        if etag:
            self.extraction_object.metadata = {**self.extraction_object.metadata, "s3_etag": etag}

        hash_content = compute_file_hash(content)
        manage_duplicate_file_content(
            source=self.extraction_object.source,
            hash_content=hash_content,
            instance=self.extraction_object,
            response_data=content,
            file_name=f"{self.extraction_object.source}-{uuid.uuid4().hex[:8]}.json",
            extra_filters={"metadata__url": self.extraction_object.metadata.get("url")},
        )

        if not self.extraction_object.resp_data:
            raise requests.exceptions.ConnectionError(f"Failed to store S3 data for {s3_uri}")

        # manage_duplicate_file_content sets revision_id + NO_CHANGE when semantic hash matches.
        if self.extraction_object.revision_id is not None:
            logger.info("S3 content unchanged (semantic hash match), skipping transform: %s", s3_uri)
            return False

        logger.info("S3 data extracted successfully")
        return True

    # ------------------------------------------------------------------ #
    # Child task builders                                                  #
    # ------------------------------------------------------------------ #

    def _make_area_tasks(self, activation_data: dict, activation_id: int) -> list:
        tasks = []
        for link in activation_data.get("links", []):
            if link.get("cpe:type") != "area":
                continue
            area_href = link.get("href", "")
            if not area_href:
                continue
            area_id = area_href.rstrip("/").split("/")[-1].split("?")[0].removesuffix(".json")
            tasks.append(
                self._make_task(
                    CharterExtractionMetadata(
                        url=self._s3_uri("activations", f"act-{activation_id}", "areas", f"{area_id}.json"),
                        type=CharterExtractionMetadataType.AREA,
                        activation_id=activation_id,
                        area_id=area_id,
                    )
                )
            )
        return tasks

    def _make_vap_tasks(self, activation_id: int) -> list:
        try:
            vap_ids = self._list_s3_prefixes(f"activations/act-{activation_id}/vaps/")
        except (BotoCoreError, ClientError):
            logger.warning(
                "Failed to list VAPs from S3 for activation %s, skipping",
                activation_id,
                extra=log_extra({"source": self.source_enum}),
                exc_info=True,
            )
            return []
        return [
            self._make_task(
                CharterExtractionMetadata(
                    url=self._s3_uri("activations", f"act-{activation_id}", "vaps", vap_id, f"{vap_id}.json"),
                    type=CharterExtractionMetadataType.VAPS,
                    activation_id=activation_id,
                )
            )
            for vap_id in vap_ids
        ]

    def _make_calibrated_dataset_tasks(self, call_ids: list[int], activation_id: int) -> list:
        tasks = []
        for call_id in call_ids:
            try:
                dataset_ids = self._list_s3_prefixes(f"calls/call-{call_id}/calibratedDatasets/")
            except (BotoCoreError, ClientError):
                logger.warning(
                    "Failed to list calibrated datasets from S3 for call %s, skipping",
                    call_id,
                    extra=log_extra({"source": self.source_enum}),
                    exc_info=True,
                )
                continue
            tasks.extend(
                self._make_task(
                    CharterExtractionMetadata(
                        url=self._s3_uri("calls", f"call-{call_id}", "calibratedDatasets", dataset_id, f"{dataset_id}.json"),
                        type=CharterExtractionMetadataType.CALIBRATED_DATASET,
                        activation_id=activation_id,
                        call_id=call_id,
                    )
                )
                for dataset_id in dataset_ids
            )
        return tasks

    def _make_task(self, metadata: CharterExtractionMetadata):
        extraction = self.init_extraction(
            metadata=metadata,
            parent_extraction=self.extraction_object,
            add_to_queue=False,
        )
        return CharterExtraction.task.s(extraction.pk).set(queue=CeleryQueue.EXTRACTION)

    def _dispatch_transform(self, tasks: list, activation_extraction_id: int) -> None:
        if tasks:
            chord(tasks, CharterTransformHandler.task.si(activation_extraction_id)).apply_async()
        else:
            CharterTransformHandler.task.apply_async(args=(activation_extraction_id,))

    # ------------------------------------------------------------------ #
    # Type handlers                                                        #
    # ------------------------------------------------------------------ #

    def handle_type_catalog(self):
        try:
            act_prefixes = self._list_s3_prefixes("activations/")
        except (BotoCoreError, ClientError):
            logger.warning(
                "Failed to list activations from S3",
                extra=log_extra({"source": self.source_enum}),
                exc_info=True,
            )
            return

        for act_prefix in act_prefixes:
            match = re.search(r"act-(\d+)", act_prefix)
            if not match:
                continue
            activation_id = int(match.group(1))
            self.init_extraction(
                metadata=CharterExtractionMetadata(
                    url=self._s3_uri("activations", f"act-{activation_id}", f"act-{activation_id}.json"),
                    type=CharterExtractionMetadataType.ACTIVATION,
                    activation_id=activation_id,
                ),
                parent_extraction=None,
                queue_name=CeleryQueue.EXTRACTION,
            )

    def handle_type_activation(self):
        self._fetch_s3_file(self.extraction_metadata.url)

        if not self.extraction_object.resp_data:
            raise requests.exceptions.ConnectionError(
                f"No response data for Charter activation extraction {self.extraction_object.pk}"
            )

        activation_id = self.extraction_metadata.activation_id
        if activation_id is None:
            raise ValueError(f"ACTIVATION extraction {self.extraction_object.pk} has no activation_id in metadata")

        try:
            with self.extraction_object.resp_data.open("rb") as f:
                activation_data = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.error(
                "Activation JSON for act-%s is unreadable",
                activation_id,
                extra=log_extra({"source": self.source_enum}),
                exc_info=True,
            )
            raise requests.exceptions.ConnectionError(f"Unreadable activation JSON for act-{activation_id}") from exc

        if not isinstance(activation_data, dict):
            logger.error(
                "Activation JSON for act-%s is not an object",
                activation_id,
                extra=log_extra({"source": self.source_enum}),
            )
            raise requests.exceptions.ConnectionError(f"Activation JSON for act-{activation_id} is not a dict")

        call_ids = activation_data.get("properties", {}).get("disaster:call_ids", [])
        all_tasks = (
            self._make_area_tasks(activation_data, activation_id)
            + self._make_vap_tasks(activation_id)
            + self._make_calibrated_dataset_tasks(call_ids, activation_id)
        )
        self._dispatch_transform(all_tasks, self.extraction_object.id)

    def handle_type_calibrated_datasets(self):
        # Legacy CALIBRATED_DATASETS container type — new activations use
        # CALIBRATED_DATASET children directly under the activation; this
        # path handles old DB records.
        call_id = self.extraction_metadata.call_id
        activation_id = self.extraction_metadata.activation_id
        parent = self.extraction_object.parent
        if parent is None:
            logger.warning(
                "CALIBRATED_DATASETS extraction has no parent, cannot trigger transform",
                extra=log_extra({"source": self.source_enum}),
            )
            return
        if call_id is None or activation_id is None:
            logger.warning(
                "CALIBRATED_DATASETS extraction %s is missing call_id or activation_id, skipping",
                self.extraction_object.pk,
                extra=log_extra({"source": self.source_enum}),
            )
            return
        tasks = self._make_calibrated_dataset_tasks([call_id], activation_id)
        self._dispatch_transform(tasks, parent.pk)

    # ------------------------------------------------------------------ #
    # Dispatch                                                             #
    # ------------------------------------------------------------------ #

    def handle_extract(self, retrigger: bool, failed_int: int | None = None):
        handler_type = self.extraction_metadata.type
        logger.info(
            "Starting Charter extraction <%s> activation_id=%s type=%s",
            self.extraction_object.pk,
            self.extraction_metadata.activation_id,
            handler_type,
        )
        match handler_type:
            case CharterExtractionMetadataType.CATALOG:
                return self.handle_type_catalog()
            case CharterExtractionMetadataType.ACTIVATION:
                return self.handle_type_activation()
            case (
                CharterExtractionMetadataType.AREA
                | CharterExtractionMetadataType.VAPS
                | CharterExtractionMetadataType.CALIBRATED_DATASET
            ):
                return self._fetch_s3_file(self.extraction_metadata.url)
            case CharterExtractionMetadataType.VAPS_CATALOG:
                return None  # container record; no fetch needed
            case CharterExtractionMetadataType.CALIBRATED_DATASETS:
                return self.handle_type_calibrated_datasets()
            case _:
                typing.assert_never(handler_type)

    @staticmethod
    @app.task(
        bind=True,
        base=RetryableTask,
        queue=CeleryQueue.EXTRACTION,
    )
    def task(celery_task: Task, extraction_id: int):
        CharterExtraction(celery_task, extraction_id).handle()
