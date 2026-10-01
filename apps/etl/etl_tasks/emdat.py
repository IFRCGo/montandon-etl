from datetime import datetime

from celery import shared_task
from django.db.models.fields.json import KT

from apps.etl.extraction.sources.emdat.extract import (
    EmdatExtraction,
    EmdatExtractionMetadata,
    EmdatExtractionMetadataType,
    EmdatExtractionParamsMetadata,
)
from apps.etl.models import ExtractionData
from apps.etl.utils import get_cluster_codes
from main.celery import CeleryQueue
from main.configs import etl_config

QUERY = """
query monty(
    $limit: Int
    $offset: Int
    $include_hist: Boolean
    $from: Int
    $to: Int
    $classif: [String!]
) {
    api_version
    public_emdat(
        cursor: { offset: $offset, limit: $limit }
        filters: { include_hist: $include_hist, from: $from, to: $to , classif: $classif}
    ) {
        total_available
        info {
            timestamp
            filters
            cursor
            version
        }
        data {
            disno
            classif_key
            group
            subgroup
            type
            subtype
            external_ids
            name
            iso
            country
            subregion
            region
            location
            origin
            associated_types
            ofda_response
            appeal
            declaration
            aid_contribution
            magnitude
            magnitude_scale
            latitude
            longitude
            river_basin
            start_year
            start_month
            start_day
            end_year
            end_month
            end_day
            total_deaths
            no_injured
            no_affected
            no_homeless
            total_affected
            reconstr_dam
            reconstr_dam_adj
            insur_dam
            insur_dam_adj
            total_dam
            total_dam_adj
            cpi
            admin_units
            entry_date
            last_update
        }
    }
}
"""


def _init_emdat_extraction(classif_key: str, from_: int, to: int, include_hist: bool | None):
    return EmdatExtraction.init_extraction(
        metadata=EmdatExtractionMetadata(
            params=EmdatExtractionParamsMetadata(
                limit=-1,
                from_=from_,
                to=to,
                include_hist=include_hist,
                classif=[classif_key],
            ),
            url=f"{etl_config.EMDAT_URL}/v1",
            type=EmdatExtractionMetadataType.QUERY,
        ),
        queue_name=CeleryQueue.EXTRACTION,
    )


def _get_latest_extraction_by_classif_key() -> dict[str, ExtractionData]:
    """
    Latest extraction for each classification key (extractions are created for single classif key)
    """
    latest_extractions = (
        ExtractionData.objects.filter(source=ExtractionData.Source.EMDAT)
        .annotate(classif_param=KT("metadata__params__classif"))
        .order_by("classif_param", "-created_at")
        .distinct("classif_param")
        .only("id", "status", "metadata")
    )
    return {
        extraction.metadata["params"]["classif"][0]: extraction
        for extraction in latest_extractions
        if len(extraction.metadata.get("params", {}).get("classif") or []) == 1
    }


@shared_task
def ext_and_transform_emdat_latest_data(**kwargs):
    current_year = datetime.now().year
    latest_extraction_by_classif_key = _get_latest_extraction_by_classif_key()

    for classif_key in get_cluster_codes():
        from_date_year = current_year
        # Re-extract from the previous failed extraction's year
        if (
            exist_extraction_object := latest_extraction_by_classif_key.get(classif_key)
        ) and exist_extraction_object.status != ExtractionData.Status.SUCCESS:
            from_date_year = exist_extraction_object.metadata["params"]["from_"]

        _init_emdat_extraction(classif_key, from_=from_date_year, to=current_year, include_hist=None)


@shared_task
def ext_and_transform_emdat_historical_data(start_date, end_date, **kwargs):
    classif_keys = get_cluster_codes()
    for year in range(start_date, end_date + 1):
        for classif_key in classif_keys:
            _init_emdat_extraction(classif_key, from_=year, to=year, include_hist=True)
