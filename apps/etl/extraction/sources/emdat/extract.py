import logging

import requests

# from celery import shared_task
from django.conf import settings
from django.core.files.base import ContentFile

from apps.etl.models import ExtractionData, HazardType

# from datetime import datetime, timedelta


logger = logging.getLogger(__name__)


# def import_hazard_data(retry_count: int, timeout: int = 30, ext_object_id: int = None, **kwargs):
def import_hazard_data(**kwargs):
    """
    Import hazard data from glide api
    """
    # logger.info(f"Importing {hazard_type} data")
    print("Import emdat data")
    query = """
        query monty ($from: Int, $to: Int, $limit: Int, $include_hist: Boolean) {
          api_version
          public_emdat(
            cursor: {limit: $limit}
            filters: {
               iso: ["NPL"],
               from: $from,
               to: $to,
               include_hist: $include_hist
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

    variables = {"year": 2023, "to": 2024, "limit": -1}
    emdat_url = "https://api.emdat.be/v1"
    paylod = {"query": query, "variables": variables}
    headers = {"Authorization": settings.EMDAT_AUTHORIZATION_KEY}

    emdat_instance = ExtractionData.objects.create(
        source=ExtractionData.Source.EMDAT,
        status=ExtractionData.Status.PENDING,
        source_validation_status=ExtractionData.ValidationStatus.NO_VALIDATION,
        hazard_type=HazardType.OTHER,
        attempt_no=0,
        resp_code=0,
    )

    try:
        emdat_instance.status = ExtractionData.Status.IN_PROGRESS
        emdat_instance.save(update_fields=["status"])

        response = requests.post(emdat_url, json=paylod, headers=headers)
        if response:
            file_name = "emdat_disaster_data.json"
            emdat_instance.resp_data.save(file_name, ContentFile(response.content))
            emdat_instance.status = ExtractionData.Status.SUCCESS
            emdat_instance.save(update_fields=["status"])

        logger.info("EMDAT data imported sucessfully")
        return emdat_instance.id

    except requests.exceptions.RequestException:
        logger.error("Extraction failed", exc_info=True, extra={"source": ExtractionData.Source.EMDAT})
        # FIXME: Check if this creates duplicate entry in Sentry. if yes, remove this.
        raise
