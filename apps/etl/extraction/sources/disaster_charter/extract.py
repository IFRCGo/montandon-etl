import json
import logging
import re
import typing
from enum import Enum

import boto3
import pydantic
import requests
from botocore.exceptions import BotoCoreError, ClientError
from celery import Task

from apps.etl.extraction.sources.base.handler import BaseExtractionV2
from apps.etl.models import ExtractionData
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
    CALIBRATED_DATASETS = "CALIBRATED_DATASETS"
    CALIBRATED_DATASET = "CALIBRATED_DATASET"


class CharterExtractionMetadata(pydantic.BaseModel):
    url: str
    type: CharterExtractionMetadataType
    activation_id: int | None = None
    area_id: str | None = None
    call_id: int | None = None


class CharterExtraction(BaseExtractionV2[CharterExtractionMetadata]):
    source_enum = ExtractionData.Source.DISASTERCHARTER
    extraction_metadata_class = CharterExtractionMetadata

    def _get_s3_client(self):
        return boto3.client(
            "s3",
            endpoint_url=etl_config.CHARTER_S3_ENDPOINT_URL,
            aws_access_key_id=etl_config.CHARTER_S3_ACCESS_KEY_ID,
            aws_secret_access_key=etl_config.CHARTER_S3_SECRET_ACCESS_KEY,
        )

    def handle_type_catalog(self):
        try:
            client = self._get_s3_client()
            paginator = client.get_paginator("list_objects_v2")
            pages = paginator.paginate(
                Bucket=etl_config.CHARTER_S3_BUCKET_NAME,
                Prefix="activations/",
                Delimiter="/",
            )
        except (BotoCoreError, ClientError):
            logger.warning(
                "Failed to list activations from S3",
                extra=log_extra({"source": self.source_enum}),
                exc_info=True,
            )
            return

        for page in pages:
            for prefix_entry in page.get("CommonPrefixes", []):
                prefix = prefix_entry.get("Prefix", "")
                match = re.search(r"act-(\d+)", prefix)
                if not match:
                    continue
                activation_id = int(match.group(1))
                activation_url = (
                    f"s3://{etl_config.CHARTER_S3_BUCKET_NAME}/activations/act-{activation_id}/act-{activation_id}.json"
                )

                self.init_extraction(
                    metadata=CharterExtractionMetadata(
                        url=activation_url,
                        type=CharterExtractionMetadataType.ACTIVATION,
                        activation_id=activation_id,
                    ),
                    parent_extraction=None,
                    queue_name=CeleryQueue.EXTRACTION,
                )

    def handle_type_activation(self):
        from celery import chord

        from apps.etl.transform.sources.disaster_charter import DisasterCharterTransformHandler

        extraction_status = self._extraction_fetch_s3(self.extraction_metadata.url)
        if not extraction_status:
            logger.warning(
                "Failed to extract Charter activation data",
                extra=log_extra({"source": self.source_enum, "extraction": self.extraction_object}),
            )
            return

        if not self.extraction_object.resp_data:
            logger.warning(
                "No response data for Charter activation",
                extra=log_extra({"source": self.source_enum, "extraction": self.extraction_object}),
            )
            return

        activation_id = self.extraction_metadata.activation_id
        with self.extraction_object.resp_data.open("rb") as f:
            activation_data = json.load(f)

        for link in activation_data.get("links", []):
            if link.get("cpe:type") != "area":
                continue
            area_href = link.get("href", "")
            if not area_href:
                continue
            area_id = area_href.rstrip("/").split("/")[-1].split("?")[0].removesuffix(".json").lower()
            area_url = f"s3://{etl_config.CHARTER_S3_BUCKET_NAME}/activations/act-{activation_id}/areas/{area_id}.json"
            self.init_extraction(
                metadata=CharterExtractionMetadata(
                    url=area_url,
                    type=CharterExtractionMetadataType.AREA,
                    activation_id=activation_id,
                    area_id=area_id,
                ),
                parent_extraction=self.extraction_object,
                queue_name=CeleryQueue.EXTRACTION,
            )

        activation_extraction_id = self.extraction_object.id

        # VAPS_CATALOG: container record so transform can find VAPs under the right parent
        vaps_catalog_url = (
            f"s3://{etl_config.CHARTER_S3_BUCKET_NAME}/activations/act-{activation_id}/act-{activation_id}-vaps.json"
        )
        vaps_catalog_extraction = self.init_extraction(
            metadata=CharterExtractionMetadata(
                url=vaps_catalog_url,
                type=CharterExtractionMetadataType.VAPS_CATALOG,
                activation_id=activation_id,
            ),
            parent_extraction=self.extraction_object,
            add_to_queue=False,
        )
        vaps_catalog_extraction.status = ExtractionData.Status.SUCCESS
        vaps_catalog_extraction.save(update_fields=["status"])

        # Discover individual VAPs by listing S3 directly
        try:
            client = self._get_s3_client()
            s3_response = client.list_objects_v2(
                Bucket=etl_config.CHARTER_S3_BUCKET_NAME,
                Prefix=f"activations/act-{activation_id}/vaps/",
                Delimiter="/",
            )
        except (BotoCoreError, ClientError):
            logger.warning(
                "Failed to list VAPs from S3 for activation %s, skipping VAP extraction",
                activation_id,
                extra=log_extra({"source": self.source_enum}),
                exc_info=True,
            )
            DisasterCharterTransformHandler.task.apply_async(args=(activation_extraction_id,))
            return

        vap_tasks = []
        for prefix_entry in s3_response.get("CommonPrefixes", []):
            prefix = prefix_entry.get("Prefix", "")
            vap_id = prefix.rstrip("/").split("/")[-1]
            if not vap_id:
                continue
            vap_url = f"s3://{etl_config.CHARTER_S3_BUCKET_NAME}/activations/act-{activation_id}/vaps/{vap_id}/{vap_id}.json"
            vap_extraction = self.init_extraction(
                metadata=CharterExtractionMetadata(
                    url=vap_url,
                    type=CharterExtractionMetadataType.VAPS,
                    activation_id=activation_id,
                ),
                parent_extraction=vaps_catalog_extraction,
                add_to_queue=False,
            )
            vap_tasks.append(CharterExtraction.task.s(vap_extraction.pk).set(queue=CeleryQueue.EXTRACTION))

        if vap_tasks:
            chord(
                vap_tasks,
                DisasterCharterTransformHandler.task.si(activation_extraction_id),
            ).apply_async()
        else:
            DisasterCharterTransformHandler.task.apply_async(args=(activation_extraction_id,))

        # Calibrated datasets: one CALIBRATED_DATASETS extraction per call
        call_ids = activation_data.get("properties", {}).get("disaster:call_ids", [])
        for call_id in call_ids:
            cal_datasets_url = (
                f"s3://{etl_config.CHARTER_S3_BUCKET_NAME}/calls/call-{call_id}/call-{call_id}-calibratedDatasets.json"
            )
            self.init_extraction(
                metadata=CharterExtractionMetadata(
                    url=cal_datasets_url,
                    type=CharterExtractionMetadataType.CALIBRATED_DATASETS,
                    activation_id=activation_id,
                    call_id=call_id,
                ),
                parent_extraction=self.extraction_object,
                queue_name=CeleryQueue.EXTRACTION,
            )

    def handle_type_area(self):
        self._extraction_fetch_s3(self.extraction_metadata.url)

    def handle_type_vaps(self):
        self._extraction_fetch_s3(self.extraction_metadata.url)

    def handle_type_calibrated_datasets(self):
        from celery import chord

        from apps.etl.transform.sources.disaster_charter import DisasterCharterTransformHandler

        extraction_status = self._extraction_fetch_s3(self.extraction_metadata.url)
        if not extraction_status:
            logger.warning(
                "Failed to extract Charter calibrated datasets collection",
                extra=log_extra({"source": self.source_enum, "extraction": self.extraction_object}),
            )
            return

        if not self.extraction_object.resp_data:
            logger.warning(
                "No response data for Charter calibrated datasets collection",
                extra=log_extra({"source": self.source_enum, "extraction": self.extraction_object}),
            )
            return

        call_id = self.extraction_metadata.call_id
        with self.extraction_object.resp_data.open("rb") as f:
            collection_data = json.load(f)

        parent = self.extraction_object.parent
        if parent is None:
            logger.warning(
                "CALIBRATED_DATASETS extraction has no parent, cannot trigger transform",
                extra=log_extra({"source": self.source_enum}),
            )
            return
        activation_extraction_id: int = parent.pk

        dataset_tasks = []
        for link in collection_data.get("links", []):
            if link.get("rel") != "item":
                continue
            href = link.get("href", "")
            if not href:
                continue
            # href is relative: "calibratedDatasets/{dataset_dir}/{dataset_dir}.json"
            parts = href.rstrip("/").split("/")
            dataset_dir = parts[-2] if len(parts) >= 2 else parts[-1]
            dataset_url = (
                f"s3://{etl_config.CHARTER_S3_BUCKET_NAME}"
                f"/calls/call-{call_id}/calibratedDatasets/{dataset_dir}/{dataset_dir}.json"
            )
            dataset_extraction = self.init_extraction(
                metadata=CharterExtractionMetadata(
                    url=dataset_url,
                    type=CharterExtractionMetadataType.CALIBRATED_DATASET,
                    activation_id=self.extraction_metadata.activation_id,
                    call_id=call_id,
                ),
                parent_extraction=self.extraction_object,
                add_to_queue=False,
            )
            dataset_tasks.append(CharterExtraction.task.s(dataset_extraction.pk).set(queue=CeleryQueue.EXTRACTION))

        if dataset_tasks:
            chord(
                dataset_tasks,
                DisasterCharterTransformHandler.task.si(activation_extraction_id),
            ).apply_async()
        else:
            DisasterCharterTransformHandler.task.apply_async(args=(activation_extraction_id,))

    def handle_type_calibrated_dataset(self):
        self._extraction_fetch_s3(self.extraction_metadata.url)

    def _extraction_fetch_s3(self, s3_uri: str) -> bool:
        from urllib.parse import urlparse

        parsed = urlparse(s3_uri)
        bucket = parsed.netloc
        key = parsed.path.lstrip("/")

        try:
            client = self._get_s3_client()
            s3_response = client.get_object(Bucket=bucket, Key=key)
            content = s3_response["Body"].read()
        except (BotoCoreError, ClientError) as exc:
            logger.error(
                "Failed to fetch from S3: %s",
                s3_uri,
                extra=log_extra({"source": self.source_enum}),
                exc_info=True,
            )
            raise requests.exceptions.ConnectionError(str(exc)) from exc

        class _S3ResponseAdapter:
            def __init__(self, data: bytes):
                self.content = data

        self.extraction_object.resp_code = 200
        self._extraction_store_data(
            extraction_object=self.extraction_object,
            response=_S3ResponseAdapter(content),  # type: ignore[arg-type]
            content_type="application/geo+json",
        )
        logger.info("S3 data extracted successfully")
        return True

    def handle_extract(self, retrigger: bool, failed_int: int | None = None):
        handler_type = self.extraction_metadata.type
        logger.info(
            f"Starting Charter extraction<{self.extraction_object.pk}> "
            f"activation_id={self.extraction_metadata.activation_id} type={handler_type}"
        )
        match handler_type:
            case CharterExtractionMetadataType.CATALOG:
                return self.handle_type_catalog()
            case CharterExtractionMetadataType.ACTIVATION:
                return self.handle_type_activation()
            case CharterExtractionMetadataType.AREA:
                return self.handle_type_area()
            case CharterExtractionMetadataType.VAPS_CATALOG:
                return None  # container record; no fetch needed
            case CharterExtractionMetadataType.VAPS:
                return self.handle_type_vaps()
            case CharterExtractionMetadataType.CALIBRATED_DATASETS:
                return self.handle_type_calibrated_datasets()
            case CharterExtractionMetadataType.CALIBRATED_DATASET:
                return self.handle_type_calibrated_dataset()
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
