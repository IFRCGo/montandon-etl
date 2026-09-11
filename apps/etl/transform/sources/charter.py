import json
import logging
from pathlib import Path

from django.conf import settings
from pystac_monty.sources.charter import CharterDataSource, CharterTransformer
from pystac_monty.sources.common import DataType, File, GenericDataSource

from apps.etl.models import ExtractionData
from apps.etl.transform.sources.handler import BaseTransformerHandler
from apps.etl.utils import write_into_temp_file
from main.celery import CeleryQueue, app
from main.configs import etl_config

logger = logging.getLogger(__name__)


class CharterTransformHandler(BaseTransformerHandler[CharterTransformer, CharterDataSource]):
    transformer_class = CharterTransformer
    transformer_schema = CharterDataSource

    @staticmethod
    def _read_json(ext_obj: ExtractionData, label: str) -> dict | list | None:
        if not ext_obj.resp_data:
            return None
        try:
            with ext_obj.resp_data.open("rb") as f:
                return json.load(f)
        except Exception:
            logger.warning("Failed to read %s extraction %s", label, ext_obj.id, exc_info=True)
            return None

    @staticmethod
    def _normalize_vap(raw: dict | list) -> list[dict]:
        if isinstance(raw, list):
            return raw
        features = raw.get("features")
        return features if features is not None else [raw]

    @classmethod
    def _collect_children(cls, parent: ExtractionData, metadata_type: str):
        return parent.child_extractions.filter(
            status=ExtractionData.Status.SUCCESS,
            metadata__type=metadata_type,
        ).order_by("id")

    @classmethod
    def get_schema_data(cls, extraction_obj: ExtractionData, dir_uuid: str) -> CharterDataSource:
        with extraction_obj.resp_data.open("rb") as f:
            activation_data = json.load(f)

        areas_data: list[dict] = []
        for area_ext in cls._collect_children(extraction_obj, "AREA"):
            raw = cls._read_json(area_ext, "area")
            if isinstance(raw, dict):
                areas_data.append(raw)

        vaps_data: list[dict] = []
        for vaps_ext in cls._collect_children(extraction_obj, "VAPS"):
            raw = cls._read_json(vaps_ext, "vaps")
            if raw is not None:
                vaps_data.extend(cls._normalize_vap(raw))
        # Old structure (backward compat): VAPS nested under a VAPS_CATALOG container.
        for catalog_ext in cls._collect_children(extraction_obj, "VAPS_CATALOG"):
            for vaps_ext in cls._collect_children(catalog_ext, "VAPS"):
                raw = cls._read_json(vaps_ext, "vaps")
                if raw is not None:
                    vaps_data.extend(cls._normalize_vap(raw))

        calibrated_datasets_data: list[dict] = []
        for dataset_ext in cls._collect_children(extraction_obj, "CALIBRATED_DATASET"):
            raw = cls._read_json(dataset_ext, "calibrated dataset")
            if not isinstance(raw, dict):
                continue
            if not raw.get("id"):
                logger.warning("Calibrated dataset extraction %s has no id, skipping", dataset_ext.id)
                continue
            calibrated_datasets_data.append(raw)
        # Old structure (backward compat): CALIBRATED_DATASET nested under a CALIBRATED_DATASETS container.
        for datasets_ext in cls._collect_children(extraction_obj, "CALIBRATED_DATASETS"):
            for dataset_ext in cls._collect_children(datasets_ext, "CALIBRATED_DATASET"):
                raw = cls._read_json(dataset_ext, "calibrated dataset")
                if not isinstance(raw, dict):
                    continue
                if not raw.get("id"):
                    logger.warning("Calibrated dataset extraction %s has no id, skipping", dataset_ext.id)
                    continue
                calibrated_datasets_data.append(raw)

        activation_data["areas"] = areas_data
        activation_data["vaps"] = vaps_data
        activation_data["calibrated_datasets"] = calibrated_datasets_data

        tmp_dir_path = Path("/tmp") / extraction_obj.get_source_display() / dir_uuid
        tmp_dir_path.mkdir(parents=True, exist_ok=True)
        data_file = write_into_temp_file(json.dumps(activation_data).encode("utf-8"), tmp_dir_path)

        return cls.transformer_schema(
            data=GenericDataSource(
                source_url=extraction_obj.url,
                input_data=File(path=data_file.name, data_type=DataType.FILE),
            ),
            eoapi_url=etl_config.EOAPI_STAC_API_PUBLIC,
        )

    @staticmethod
    def _should_skip_transform(activation_ext: ExtractionData) -> bool:
        if activation_ext.source_validation_status != ExtractionData.ValidationStatus.NO_CHANGE:
            return False
        return (
            not activation_ext.child_extractions.filter(
                metadata__type__in=["AREA", "VAPS", "CALIBRATED_DATASET"],
            )
            .exclude(source_validation_status=ExtractionData.ValidationStatus.NO_CHANGE)
            .exists()
        )

    @staticmethod
    @app.task(queue=CeleryQueue.TRANSFORM)
    def task(extraction_id: int) -> None:
        activation_ext = ExtractionData.objects.get(id=extraction_id)
        if CharterTransformHandler._should_skip_transform(activation_ext):
            logger.info(
                "Skipping transform for activation extraction %s: no data changed",
                extraction_id,
            )
            return
        CharterTransformHandler().handle_transformation(extraction_id, settings.CHARTER_TRANSFORMER_VERSION)
