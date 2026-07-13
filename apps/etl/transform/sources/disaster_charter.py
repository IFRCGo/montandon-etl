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


class DisasterCharterTransformHandler(BaseTransformerHandler[CharterTransformer, CharterDataSource]):
    transformer_class = CharterTransformer
    transformer_schema = CharterDataSource

    @classmethod
    def get_schema_data(cls, extraction_obj: ExtractionData, dir_uuid: str) -> CharterDataSource:
        with extraction_obj.resp_data.open("rb") as f:
            activation_data = json.load(f)

        areas_data: list[dict] = []
        vaps_data: list[dict] = []
        acquisitions_data: list[dict] = []

        # Areas are always direct children of the activation.
        for area_ext in extraction_obj.child_extractions.filter(
            status=ExtractionData.Status.SUCCESS,
            metadata__type="AREA",
        ).order_by("id"):
            if not area_ext.resp_data:
                continue
            try:
                with area_ext.resp_data.open("rb") as f:
                    area_data = json.load(f)
                if isinstance(area_data, dict):
                    areas_data.append(area_data)
            except Exception:
                logger.warning("Failed to read area extraction %s", area_ext.id, exc_info=True)

        def _collect_vap(vaps_ext) -> None:
            if not vaps_ext.resp_data:
                return
            try:
                with vaps_ext.resp_data.open("rb") as f:
                    vaps_raw = json.load(f)
                if isinstance(vaps_raw, list):
                    vaps_data.extend(vaps_raw)
                elif isinstance(vaps_raw, dict):
                    features = vaps_raw.get("features")
                    if features is not None:
                        vaps_data.extend(features)
                    else:
                        vaps_data.append(vaps_raw)
            except Exception:
                logger.warning("Failed to read vaps extraction %s", vaps_ext.id, exc_info=True)

        # New structure: VAPS as direct children of the activation.
        for vaps_ext in extraction_obj.child_extractions.filter(
            status=ExtractionData.Status.SUCCESS,
            metadata__type="VAPS",
        ).order_by("id"):
            _collect_vap(vaps_ext)

        # Old structure (backward compat): VAPS nested under a VAPS_CATALOG container.
        for vaps_catalog_ext in extraction_obj.child_extractions.filter(
            status=ExtractionData.Status.SUCCESS,
            metadata__type="VAPS_CATALOG",
        ).order_by("id"):
            for vaps_ext in vaps_catalog_ext.child_extractions.filter(
                status=ExtractionData.Status.SUCCESS,
                metadata__type="VAPS",
            ).order_by("id"):
                _collect_vap(vaps_ext)

        def _collect_acquisition(acq_ext) -> None:
            if not acq_ext.resp_data:
                return
            try:
                with acq_ext.resp_data.open("rb") as f:
                    acq_data = json.load(f)
                if not isinstance(acq_data, dict):
                    return
                if not acq_data.get("id"):
                    logger.warning("Acquisition %s has no id, skipping", acq_ext.id)
                    return
                acquisitions_data.append(acq_data)
            except Exception:
                logger.warning("Failed to read acquisition extraction %s", acq_ext.id, exc_info=True)

        # New structure: ACQUISITION as direct children of the activation.
        for acq_ext in extraction_obj.child_extractions.filter(
            status=ExtractionData.Status.SUCCESS,
            metadata__type="ACQUISITION",
        ).order_by("id"):
            _collect_acquisition(acq_ext)

        # Old structure (backward compat): ACQUISITION nested under an ACQUISITIONS container.
        for acquisitions_ext in extraction_obj.child_extractions.filter(
            status=ExtractionData.Status.SUCCESS,
            metadata__type="ACQUISITIONS",
        ).order_by("id"):
            for acq_ext in acquisitions_ext.child_extractions.filter(
                status=ExtractionData.Status.SUCCESS,
                metadata__type="ACQUISITION",
            ).order_by("id"):
                _collect_acquisition(acq_ext)

        activation_data["areas"] = areas_data
        activation_data["vaps"] = vaps_data
        activation_data["calibrated_datasets"] = acquisitions_data

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
    @app.task(queue=CeleryQueue.TRANSFORM)
    def task(extraction_id: int) -> None:
        activation_ext = ExtractionData.objects.get(id=extraction_id)

        activation_unchanged = activation_ext.source_validation_status == ExtractionData.ValidationStatus.NO_CHANGE
        has_changed_children = (
            activation_ext.child_extractions.filter(
                metadata__type__in=["AREA", "VAPS", "ACQUISITION"],
            )
            .exclude(source_validation_status=ExtractionData.ValidationStatus.NO_CHANGE)
            .exists()
        )

        if activation_unchanged and not has_changed_children:
            logger.info(
                "Skipping transform for activation extraction %s: all etags matched, no data changed",
                extraction_id,
            )
            return

        DisasterCharterTransformHandler().handle_transformation(extraction_id, settings.CHARTER_TRANSFORMER_VERSION)
