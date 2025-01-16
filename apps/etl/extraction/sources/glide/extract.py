import logging
from datetime import datetime, timedelta

import requests
from celery import shared_task

from apps.etl.extraction.sources.base.extract import Extraction
from apps.etl.models import ExtractionData

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def import_hazard_data(self, hazard_type: str, hazard_type_str: str, **kwargs):
    from apps.etl.tasks import store_extraction_data

    """
    Import hazard data from glide api
    """
    logger.info(f"Importing {hazard_type} data")

    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    # TODO make the url dynamic
    # glide_url = f"https://www.glidenumber.net/glide/jsonglideset.jsp?fromyear=2024&frommonth=10&fromday=01&toyear=2024&frommonth=12&today=31&events={hazard_type}"  # noqa: E501
    glide_url = f"https://www.glidenumber.net/glide/jsonglideset.jsp?fromyear={yesterday.year}&frommonth={yesterday.month}&fromday={yesterday.day}&toyear={today.year}&frommonth={today.month}&today={today.day}&events={hazard_type}"  # noqa: E501

    # Create a Extraction object in the begining
    instance_id = kwargs.get("instance_id", None)
    retry_count = kwargs.get("retry_count", None)

    glide_instance = (
        ExtractionData.objects.get(id=instance_id)
        if instance_id
        else ExtractionData.objects.create(
            source=ExtractionData.Source.GLIDE,
            status=ExtractionData.Status.PENDING,
            source_validation_status=ExtractionData.ValidationStatus.NO_VALIDATION,
            hazard_type=hazard_type_str,
            attempt_no=0,
            resp_code=0,
        )
    )

    # Extract the data from api.
    glide_extraction = Extraction(url=glide_url)
    response = None
    try:
        response = glide_extraction.pull_data(
            source=ExtractionData.Source.GLIDE,
            ext_object_id=glide_instance.id,
            retry_count=retry_count if retry_count else 1,
        )
    except requests.exceptions.RequestException as exc:
        self.retry(exc=exc, kwargs={"instance_id": glide_instance.id, "retry_count": self.request.retries})

    if response:
        # Save the extracted data into the existing glide object
        glide_instance = store_extraction_data(
            response=response,
            source=ExtractionData.Source.GLIDE,
            validate_source_func=None,
            instance_id=glide_instance.id,
        )
        with open(glide_instance.resp_data.path, "r") as file:
            data = file.read()

        logger.info(f"{hazard_type} data imported sucessfully")
        return {"extraction_id": glide_instance.id, "extracted_data": data}
