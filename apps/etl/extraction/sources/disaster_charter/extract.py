import json
import logging
import re
import typing
from enum import Enum

import pydantic
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


class CharterExtractionMetadata(pydantic.BaseModel):
    url: str
    type: CharterExtractionMetadataType
    activation_id: int | None = None
    area_id: str | None = None


class CharterExtraction(BaseExtractionV2[CharterExtractionMetadata]):
    source_enum = ExtractionData.Source.DISASTERCHARTER
    extraction_metadata_class = CharterExtractionMetadata

    def handle_type_catalog(self):
        extraction_status = self._extraction_fetch_url(
            self.extraction_metadata.url,
            headers={"Accept": "application/json"},
        )
        if not extraction_status:
            logger.warning(
                "Failed to extract Charter catalog",
                extra=log_extra({"source": self.source_enum, "extraction": self.extraction_object}),
            )
            return

        if not self.extraction_object.resp_data:
            logger.warning(
                "No response data for Charter catalog",
                extra=log_extra({"source": self.source_enum, "extraction": self.extraction_object}),
            )
            return

        with self.extraction_object.resp_data.open("rb") as f:
            catalog_data = json.load(f)

        for link in catalog_data.get("links", []):
            if link.get("rel") != "item":
                continue
            href = link.get("href", "")
            match = re.search(r"act-(\d+)", href)
            if not match:
                continue
            activation_id = int(match.group(1))
            activation_url = f"{etl_config.CHARTER_SUPERVISOR_URL}/api/activations/act-{activation_id}"
            # activation_url = f"{etl_config.CHARTER_SUPERVISOR_URL}/api/activations/act-1000"
            self.init_extraction(
                metadata=CharterExtractionMetadata(
                    url=activation_url,
                    type=CharterExtractionMetadataType.ACTIVATION,
                    activation_id=activation_id,
                ),
                parent_extraction=self.extraction_object,
                queue_name=CeleryQueue.EXTRACTION,
            )

    def handle_type_activation(self):
        extraction_status = self._extraction_fetch_url(
            self.extraction_metadata.url,
            headers={"Accept": "application/json"},
        )
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
            self.init_extraction(
                metadata=CharterExtractionMetadata(
                    url=area_href,
                    type=CharterExtractionMetadataType.AREA,
                    activation_id=activation_id,
                    area_id=area_id,
                ),
                parent_extraction=self.extraction_object,
                queue_name=CeleryQueue.EXTRACTION,
            )

        vaps_catalog_url = f"{etl_config.CHARTER_SUPERVISOR_URL}/api/activations/act-{activation_id}/vaps"
        # vaps_catalog_url = "https://supervisor.disasterscharter.org/api/activations/act-1000/vaps/"
        self.init_extraction(
            metadata=CharterExtractionMetadata(
                url=vaps_catalog_url,
                type=CharterExtractionMetadataType.VAPS_CATALOG,
                activation_id=activation_id,
            ),
            parent_extraction=self.extraction_object,
            queue_name=CeleryQueue.EXTRACTION,
        )

    def handle_type_area(self):
        self._extraction_fetch_url(
            self.extraction_metadata.url,
            headers={"Accept": "application/json"},
        )

    def handle_type_vaps_catalog(self):
        from celery import chord

        from apps.etl.transform.sources.disaster_charter import DisasterCharterTransformHandler

        extraction_status = self._extraction_fetch_url(
            self.extraction_metadata.url,
            headers={"Accept": "application/json"},
        )

        activation_extraction_id = self.extraction_object.parent.id

        if not extraction_status or not self.extraction_object.resp_data:
            logger.warning(
                "Failed to extract Charter vaps catalog",
                extra=log_extra({"source": self.source_enum, "extraction": self.extraction_object}),
            )
            # DisasterCharterTransformHandler.task.apply_async(args=(activation_extraction_id,))
            return

        activation_id = self.extraction_metadata.activation_id
        with self.extraction_object.resp_data.open("rb") as f:
            vaps_catalog_data = json.load(f)

        vap_tasks = []
        for link in vaps_catalog_data.get("links", []):
            if link.get("rel") != "item":
                continue
            href = link.get("href", "")
            if not href:
                continue

            vap_url = f"{etl_config.CHARTER_SUPERVISOR_URL}/api/activations/act-{activation_id}/vaps/{href}"
            # vap_url = "https://raw.githubusercontent.com/IFRCGo/monty-stac-extension/f5582bb8eaacd55b8629550b3c14c32034968076/docs/model/sources/Charter/act-1000-vap-1144-1.json"

            vap_extraction = self.init_extraction(
                metadata=CharterExtractionMetadata(
                    url=vap_url,
                    type=CharterExtractionMetadataType.VAPS,
                    activation_id=activation_id,
                ),
                parent_extraction=self.extraction_object,
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

    def handle_type_vaps(self):
        self._extraction_fetch_url(
            self.extraction_metadata.url,
            headers={"Accept": "application/json"},
        )

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
                return self.handle_type_vaps_catalog()
            case CharterExtractionMetadataType.VAPS:
                return self.handle_type_vaps()
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
