import json

from celery import shared_task
from pystac_monty.sources.emdat import EMDATDataSource, EMDATTransformer

from apps.etl.models import ExtractionData
from apps.etl.transform.sources.base import transform_data
from apps.etl.utils import read_file_data


@shared_task
def transform_emdat_data(extraction_id, **kwargs):
    ext_instance = ExtractionData.objects.get(id=extraction_id)
    data = read_file_data(ext_instance.resp_data)
    json_data = json.loads(data)

    transform_data(
        ExtractionData.Source.EMDAT,
        EMDATTransformer,
        EMDATDataSource,
        extraction_id,
        json_data,
    )
