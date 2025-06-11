from datetime import datetime

from celery import shared_task

from apps.etl.extraction.sources.emdat.extract import (
    EmdatExtraction,
    EmdatExtractionMetadata,
    EmdatExtractionMetadataType,
    EmdatExtractionParamsMetadata,
)
from apps.etl.models import ExtractionData
from apps.etl.utils import get_cluster_codes
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


@shared_task
def ext_and_transform_emdat_latest_data(**kwargs):
    exist_extraction_object = (
        ExtractionData.objects.filter(source=ExtractionData.Source.EMDAT).order_by("-created_at").first()
    )

    from_date_year = datetime.now().year
    if exist_extraction_object:
        if not exist_extraction_object.status == ExtractionData.Status.SUCCESS:
            from_date_year = exist_extraction_object.metadata["params"]["from_"]

    extraction_object = EmdatExtraction.init_extraction(
        metadata=EmdatExtractionMetadata(
            params=EmdatExtractionParamsMetadata(
                limit=-1,
                from_=from_date_year,
                to=datetime.now().year,
                include_hist=None,
                classif=get_cluster_codes(),
            ),
            url=f"{etl_config.EMDAT_URL}/v1",
            type=EmdatExtractionMetadataType.QUERY,
        ),
    )
    EmdatExtraction.task.delay(extraction_object.id)


@shared_task
def ext_and_transform_emdat_historical_data(**kwargs):
    for i in range(etl_config.EMDAT_START_YEAR, etl_config.EMDAT_END_YEAR + 1):
        extraction_object = EmdatExtraction.init_extraction(
            metadata=EmdatExtractionMetadata(
                params=EmdatExtractionParamsMetadata(
                    limit=-1,
                    from_=i,
                    to=i,
                    include_hist=True,
                    classif=get_cluster_codes(),
                ),
                url=f"{etl_config.EMDAT_URL}/v1",
                type=EmdatExtractionMetadataType.QUERY,
            ),
        )

        EmdatExtraction.task.delay(extraction_object.id)
