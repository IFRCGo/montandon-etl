
import logging
from datetime import datetime, timedelta

import requests
from celery import shared_task

from apps.etl.extraction.sources.base.extract import Extraction
from apps.etl.models import ExtractionData, HazardType
from apps.etl.extraction.sources.base.utils import store_extraction_data

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def import_hazard_data(self,  **kwargs):

    """
    Import hazard data from glide api
    """
    logger.info(f"Importing {HazardType.CYCLONE} data")

    noaa_active_event_data = "https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-stewardship-ibtracs/v04r01/access/csv/ibtracs.ACTIVE.list.v04r01.csv"  # noqa E261
    # Create a Extraction object in the begining
    instance_id = kwargs.get("instance_id", None)
    retry_count = kwargs.get("retry_count", None)

    noaa_instance = (
        ExtractionData.objects.get(id=instance_id)
        if instance_id
        else ExtractionData.objects.create(
            source=ExtractionData.Source.IBTRACS,
            status=ExtractionData.Status.PENDING,
            source_validation_status=ExtractionData.ValidationStatus.NO_VALIDATION,
            hazard_type=HazardType.CYCLONE,
            attempt_no=0,
            resp_code=0,
        )
    )
    
    noaa_url = noaa_active_event_data
  
    # Extract the data from api.
    noaa_extraction = Extraction(url=noaa_url)
    response = None
    try:
        response = noaa_extraction.pull_data(
            source=ExtractionData.Source.IBTRACS,
            ext_object_id=noaa_instance.id,
            retry_count=retry_count if retry_count else 1,
        )
    except requests.exceptions.RequestException as exc:
        self.retry(exc=exc, kwargs={"instance_id": noaa_instance.id, "retry_count": self.request.retries})


    if response:
        # Save the extracted data into the existing glide object
        noaa_instance = store_extraction_data(
            response=response,
            source=ExtractionData.Source.IBTRACS,
            validate_source_func=None,
            instance_id=noaa_instance.id,
        )
        with open(noaa_instance.resp_data.path, "r") as file:
            data = file.read()

        logger.info(f"{HazardType.CYCLONE} data imported successfully")
        return {"extraction_id": noaa_instance.id, "extracted_data": data}
