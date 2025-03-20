import json
import logging
import uuid
from datetime import datetime

import requests
from celery import shared_task
from django.conf import settings
from django.core.files.base import ContentFile

from apps.etl.models import ExtractionData, HazardType
from main.logging import log_extra

logger = logging.getLogger(__name__)


@shared_task
def extract_emdat_latest_data():
    to_year = datetime.now().year
    from_year = int(settings.EMDAT_START_YEAR)
    # ref: https://files.emdat.be/docs/emdat_api_cookbook.pdfhttps://files.emdat.be/docs/emdat_api_cookbook.pdf
    variables = {"limit": -1, "from": from_year, "to": to_year}
    return import_hazard_data(variables)


@shared_task
def extract_emdat_historical_data():
    variables = {"limit": -1, "include_hist": True}
    return import_hazard_data(variables)


@shared_task
def import_hazard_data(variables, **kwargs):
    """
    Import hazard data from glide api
    """
    logger.info("Importing EMDAT data")
    query = """
        query monty ($limit: Int, $offset: Int, $include_hist: Boolean, $from: Int, $to: Int) {
          api_version
          public_emdat(
            cursor: {
                offset: $offset,
                limit: $limit
            }
            filters: {
               include_hist: $include_hist
               from: $from
               to: $to
         }
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

    EMDAT_URL = f"{settings.EMDAT_URL}"
    HEADERS = {"Authorization": settings.EMDAT_AUTHORIZATION_KEY}

    # Create new extraction object for each extraction
    emdat_instance = ExtractionData.objects.create(
        source=ExtractionData.Source.EMDAT,
        status=ExtractionData.Status.PENDING,
        source_validation_status=ExtractionData.ValidationStatus.NO_VALIDATION,
        hazard_type=HazardType.OTHER,
        attempt_no=0,
        trace_id=str(uuid.uuid4()),
        resp_code=0,
    )

    try:
        # Set extraction status to progress
        emdat_instance.status = ExtractionData.Status.IN_PROGRESS
        emdat_instance.save(update_fields=["status"])

        paylod = {"query": query, "variables": variables}
        response = requests.post(EMDAT_URL, json=paylod, headers=HEADERS)
        response.raise_for_status()

        # Save the extraction data
        if response and response.status_code == 200:
            file_name = "emdat_disaster_data.json"
            emdat_instance.resp_data.save(file_name, ContentFile(response.content))

            # Set extraction status to success
            emdat_instance.status = ExtractionData.Status.SUCCESS
            response_content_json = json.loads(response.content)

            # if data is empty set validation status to No Data
            if not response_content_json["data"]["public_emdat"]:
                emdat_instance.source_validation_status = ExtractionData.ValidationStatus.NO_DATA

            emdat_instance.save(update_fields=["status", "source_validation_status"])

        logger.info("EMDAT data imported sucessfully")
        return emdat_instance.id

    except requests.exceptions.RequestException:
        # Set extraction status to Fail
        emdat_instance.status = ExtractionData.Status.FAILED
        emdat_instance.save(update_fields=["status"])
        logger.error("Extraction failed", exc_info=True, extra=log_extra({"source": ExtractionData.Source.EMDAT}))
        # FIXME: Check if this creates duplicate entry in Sentry. if yes, remove this.
        raise
