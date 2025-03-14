from datetime import datetime

from celery import chain, shared_task
from django.conf import settings

from apps.etl.extraction.sources.emdat.extract import EMDATExtraction
from apps.etl.transform.sources.emdat import EMDATTransformHandler

QUERY = """
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


@shared_task
def ext_and_transform_emdat_latest_data(**kwargs):
    to_year = datetime.now().year
    from_year = int(settings.EMDAT_START_YEAR)
    variables = {"limit": -1, "from": from_year, "to": to_year}

    chain(EMDATExtraction.task.s(QUERY, variables), EMDATTransformHandler.task.s()).apply_async()


@shared_task
def ext_and_transform_emdat_historical_data(**kwargs):
    variables = {"limit": -1, "include_hist": True}
    chain(EMDATExtraction.task.s(QUERY, variables), EMDATTransformHandler.task.s()).apply_async()
