import requests
import logging
import typing
import json

from celery import chain, shared_task
from datetime import datetime, timedelta
from django.core.management import call_command

from apps.etl.extract import Extraction
from apps.etl.models import ExtractionData, HazardType
from apps.etl.tasks import store_extraction_data

logger = logging.getLogger(__name__)


@shared_task
def fetch_glide_data():
    call_command("import_glide_data")


@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def import_glide_hazard_data(self, hazard_type: str, hazard_type_str: str, **kwargs):
    """
    Import hazard data from gdacs api
    """
    logger.info(f"Importing {hazard_type} data")

    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    # gdacs_url = f"https://www.glidenumber.net/glide/jsonglideset.jsp?fromyear={yesterday.year}&frommonth={yesterday.month}&fromday={yesterday.day}&toyear={today.year}&frommonth={today.month}&today={today.day}&events={hazard_type}" # noqa: E501
    gdacs_url = "https://www.glidenumber.net/glide/jsonglideset.jsp?fromyear=2024&frommonth=01&fromday=01&toyear=2024&frommonth=12&today=31&events=EQ"

    # Create a Extraction object in the begining
    instance_id = kwargs.get("instance_id", None)
    retry_count = kwargs.get("retry_count", None)

    gdacs_instance = (
        ExtractionData.objects.get(id=instance_id)
        if instance_id
        else ExtractionData.objects.create(
            source=ExtractionData.Source.GDACS,
            status=ExtractionData.Status.PENDING,
            source_validation_status=ExtractionData.ValidationStatus.NO_VALIDATION,
            hazard_type=hazard_type_str,
            attempt_no=0,
            resp_code=0,
        )
    )

    # Extract the data from api.
    gdacs_extraction = Extraction(url=gdacs_url)
    response = None
    try:
        response = gdacs_extraction.pull_data(
            source=ExtractionData.Source.GDACS,
            ext_object_id=gdacs_instance.id,
            retry_count=retry_count if retry_count else 1,
        )
    except requests.exceptions.RequestException as exc:
        self.retry(exc=exc, kwargs={"instance_id": gdacs_instance.id, "retry_count": self.request.retries})

    if response:
        resp_data_content = response["resp_data"].content

        # decode the byte object(response data) into json
        try:
            resp_data_json = json.loads(resp_data_content.decode("utf-8"))
        except json.JSONDecodeError as e:
            logger.info(f"JSON decode error: {e}")
            resp_data_json = {}

        # Save the extracted data into the existing gdacs object
        gdacs_instance = store_extraction_data(
            response=response,
            validate_source_func=None,
            instance_id=gdacs_instance.id,
        )

        # # Fetch geometry and population exposure data
        # if gdacs_instance.resp_code == 200 and gdacs_instance.status == ExtractionData.Status.SUCCESS and resp_data_json:
        #     for feature in resp_data_json["features"]:
        #         event_id = feature["properties"]["eventid"]
        #         episode_id = feature["properties"]["episodeid"]
        #         footprint_url = feature["properties"]["url"]["geometry"]
        #         if hazard_type == HazardType.CYCLONE and event_id and episode_id:
        #             footprint_url = f"https://www.gdacs.org/contentdata/resources/{hazard_type_str}/{event_id}/geojson_{event_id}_{episode_id}.geojson"  # noqa: E501

        #         event_workflow = chain(
        #             fetch_event_data.s(
        #                 parent_id=gdacs_instance.id,
        #                 event_id=event_id,
        #                 hazard_type=hazard_type,
        #             ),
        #             transform_event_data.s(),
        #         )
        #         event_result = event_workflow.apply_async()

        #         geo_workflow = chain(
        #             fetch_gdacs_geometry_data.s(
        #                 parent_id=gdacs_instance.id,
        #                 footprint_url=footprint_url,
        #             ),
        #             transform_geo_data.s(event_result.parent.id),
        #         )
        #         geo_result = geo_workflow.apply_async()

        #         impact_workflow = chain(
        #             fetch_event_data.s(
        #                 parent_id=gdacs_instance.id,
        #                 event_id=event_id,
        #                 hazard_type=hazard_type,
        #             ),
        #             transform_impact_data.s(),
        #         )
        #         impact_result = impact_workflow.apply_async()

        #         load_data.s(event_result.id, geo_result.id, impact_result.id).apply_async()

        logger.info(f"{hazard_type} data imported sucessfully")
