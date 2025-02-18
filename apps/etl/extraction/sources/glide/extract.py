import logging
from datetime import datetime

import requests
from celery import shared_task

from apps.etl.extraction.sources.base.extract import Extraction
from apps.etl.extraction.sources.base.utils import store_extraction_data
from apps.etl.models import ExtractionData

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def import_hazard_data(self, hazard_type: str, hazard_type_str: str, **kwargs):
    """
    Import hazard data from glide api
    """
    logger.info(f"Importing {hazard_type} data")

    to_date = datetime.now().date()
    ext_object = (
        ExtractionData.objects.filter(
            source=ExtractionData.Source.GLIDE,
            status=ExtractionData.Status.SUCCESS,
            resp_data__isnull=False,
        )
        .order_by("-created_at")
        .first()
    )
    # glide_url = f"https://www.glidenumber.net/glide/jsonglideset.jsp?fromyear=2024&frommonth=10&fromday=01&toyear=2024&frommonth=12&to_date=31&events={hazard_type}"  # noqa: E501
    if ext_object:
        glide_url = f"https://www.glidenumber.net/glide/jsonglideset.jsp?fromyear={ext_object.created_at.year}&frommonth={ext_object.created_at.month}&fromday={ext_object.created_at.day}&toyear={to_date.year}&frommonth={to_date.month}&to_date={to_date.day}&events={hazard_type}"  # noqa: E501
    else:
        glide_url = f"https://www.glidenumber.net/glide/jsonglideset.jsp?toyear={to_date.year}&frommonth={to_date.month}&to_date={to_date.day}&events={hazard_type}"  # noqa: E501

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

        logger.info(f"{hazard_type} data imported sucessfully")
        return glide_instance.id
