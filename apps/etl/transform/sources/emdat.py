import json
import logging

from celery import shared_task
from pystac_monty.sources.emdat import EMDATDataSource, EMDATTransformer

from apps.etl.models import ExtractionData
from apps.etl.transform.sources.base import transform_data
from apps.etl.utils import read_file_data

logger = logging.getLogger(__name__)


@shared_task
def transform_emdat_data(extraction_id, **kwargs):
    """
    Transform extracted data from emdat graphql api to STAC item .
    """
    ext_instance = ExtractionData.objects.filter(id=extraction_id).first()
    if ext_instance and ext_instance.source_validation_status == ExtractionData.ValidationStatus.NO_DATA:
        logger.warning(
            "No data available",
        )
        return
    data = read_file_data(ext_instance.resp_data)
    json_data = json.loads(data)

    transform_data(
        ExtractionData.Source.EMDAT,
        EMDATTransformer,
        EMDATDataSource,
        extraction_id,
        json_data,
    )
