import logging
from datetime import datetime, timedelta

import requests
from celery import shared_task

from apps.etl.models import HazardType
from apps.etl.extraction.sources.base.extract import Extraction
from apps.etl.extraction.sources.base.utils import store_extraction_data
from apps.etl.models import ExtractionData

logger = logging.getLogger(__name__)


def ext_and_transform_glide_latest_data(hazard_type, hazard_type_str):
    def _ext_and_transform_glide_latest_data(hazard_type, hazard_type_str):
        ext_object = (
            ExtractionData.objects.filter(
                source=ExtractionData.Source.GLIDE,
                hazard_type=hazard_type,
                status=ExtractionData.Status.SUCCESS,
                resp_data__isnull=False,
            )
            .order_by("-created_at")
            .first()
        )
        if ext_object:
            from_date = ext_object.created_at.date()
        else:
            # Fetch data up to one week at the begining.
            from_date = datetime.today() - timedelta(days=7)

        to_date = datetime.today().date()
        url = f"https://www.glidenumber.net/glide/jsonglideset.jsp?fromyear={from_date.year}&frommonth={from_date.month}&fromday={from_date.day}&toyear={to_date.year}&frommonth={to_date.month}&to_date={to_date.day}&events={hazard_type}"  # noqa: E501
        import_glide_hazard_data.delay(hazard_type, hazard_type_str, url)

    _ext_and_transform_glide_latest_data("EQ", HazardType.EARTHQUAKE)
    _ext_and_transform_glide_latest_data("TC", HazardType.CYCLONE)
    _ext_and_transform_glide_latest_data("FL", HazardType.FLOOD)
    _ext_and_transform_glide_latest_data("DR", HazardType.DROUGHT)
    _ext_and_transform_glide_latest_data("WF", HazardType.WILDFIRE)
    _ext_and_transform_glide_latest_data("VO", HazardType.VOLCANO)
    _ext_and_transform_glide_latest_data("TS", HazardType.TSUNAMI)
    _ext_and_transform_glide_latest_data("CW", HazardType.COLDWAVE)
    _ext_and_transform_glide_latest_data("EP", HazardType.EPIDEMIC)
    _ext_and_transform_glide_latest_data("EC", HazardType.EXTRATROPICAL_CYCLONE)
    _ext_and_transform_glide_latest_data("ET", HazardType.EXTREME_TEMPERATURE)
    _ext_and_transform_glide_latest_data("FR", HazardType.FIRE)
    _ext_and_transform_glide_latest_data("FF", HazardType.FLASH_FLOOD)
    _ext_and_transform_glide_latest_data("HT", HazardType.HEAT_WAVE)
    _ext_and_transform_glide_latest_data("IN", HazardType.INSECT_INFESTATION)
    _ext_and_transform_glide_latest_data("LS", HazardType.LANDSLIDE)
    _ext_and_transform_glide_latest_data("MS", HazardType.MUD_SLIDE)
    _ext_and_transform_glide_latest_data("ST", HazardType.SEVERE_LOCAL_STROM)
    _ext_and_transform_glide_latest_data("SL", HazardType.SLIDE)
    _ext_and_transform_glide_latest_data("AV", HazardType.SNOW_AVALANCHE)
    _ext_and_transform_glide_latest_data("SS", HazardType.STORM)
    _ext_and_transform_glide_latest_data("AC", HazardType.TECH_DISASTER)
    _ext_and_transform_glide_latest_data("TO", HazardType.TORNADO)
    _ext_and_transform_glide_latest_data("VW", HazardType.VIOLENT_WIND)
    _ext_and_transform_glide_latest_data("WV", HazardType.WAVE_SURGE)


def ext_and_transform_glide_historical_data(hazard_type, hazard_type_str):
    to_date = datetime.today().date()
    url = f"https://www.glidenumber.net/glide/jsonglideset.jsp?toyear={to_date.year}&frommonth={to_date.month}&to_date={to_date.day}&events={hazard_type}"  # noqa: E501
    import_glide_hazard_data(hazard_type, hazard_type_str, url)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def import_glide_hazard_data(self, hazard_type: str, hazard_type_str: str, url: str, **kwargs):
    """
    Import hazard data from glide api
    """
    logger.info(f"Importing GDACS - {hazard_type} data")

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
    glide_extraction = Extraction(url=url)
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
