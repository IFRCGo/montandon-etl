from datetime import timedelta

from celery import chain, shared_task
from dateutil.relativedelta import relativedelta
from django.utils import timezone

from apps.etl.extraction.sources.alert_hub.extract import (
    AlertHubExtraction,
    AlertHubExtractionMetadata,
    AlertHubExtractionMetadataType,
    AlertHubExtractionParamsMetadata,
)
from apps.etl.models import ExtractionData
from main.celery import CeleryQueue
from main.configs import etl_config

QUERY = """
query Alerts($filters: AlertFilter, $pagination: OffsetPaginationInput) {
  public {
    historicalAlerts(filters: $filters, pagination: $pagination) {
      limit
      offset
      count
      items {
        id
        sent
        status
        msgType
        identifier
        sender
        source
        scope
        restriction
        addresses
        code
        note
        references
        incidents
        url

        country {
          id
          name
          iso3
        }

        admin1s {
          id
          name
          isUnknown
          alertCount
        }

        info {
          id
          alertId
          event
          language
          category
          severity
          urgency
          certainty
          headline
          description
          instruction
          onset
          effective
          expires
          eventCode
          areas {
            id
            alertInfoId
            areaDesc
            polygons {
              id
              value
              valuePolygon
            }
            geocodes {
              id
              alertInfoAreaId
              valueName
              value
            }
          }
        }

        infos {
          id
          alertId
          event
          language
          category
          severity
          urgency
          certainty
          headline
          description
          instruction
          onset
          effective
          expires
          eventCode
        }
      }
    }
  }
}
"""


@shared_task
def ext_and_transform_alert_hub_latest_data(**kwargs):
    extraction_object = ExtractionData.objects.filter(source=ExtractionData.Source.ALERTHUB).order_by("-created_at").first()
    from_datetime = timezone.now() - timedelta(days=1)
    if extraction_object:
        if extraction_object.status == ExtractionData.Status.SUCCESS:
            from_datetime = extraction_object.metadata["params"]["end"]
        elif extraction_object.status == ExtractionData.Status.FAILED:
            from_datetime = extraction_object.metadata["params"]["start"]

    AlertHubExtraction.init_extraction(
        metadata=AlertHubExtractionMetadata(
            params=AlertHubExtractionParamsMetadata(
                start=str(from_datetime),
                end=str(timezone.now()),
                limit=0,
                offset=0,
            ),
            url=f"{etl_config.ALERT_HUB_URL}/graphql/",
            type=AlertHubExtractionMetadataType.QUERY,
        ),
        queue_name=CeleryQueue.EXTRACTION,
    )


@shared_task
def schedule_alert_hub_historical_extraction(start_date, end_date):
    """
    Split historical extraction into sequential calendar-month chunks
    without exceeding the user-provided boundaries.
    """

    tasks = []
    current = start_date

    while current < end_date:
        next_month_boundary = current.replace(day=1) + relativedelta(months=1)
        next_boundary = min(next_month_boundary, end_date)

        tasks.append(
            ext_and_transform_alert_hub_historical_data.si(
                start_date=current,
                end_date=next_boundary,
            )
        )

        current = next_boundary

    chain(*tasks).apply_async()


@shared_task
def ext_and_transform_alert_hub_historical_data(start_date, end_date):
    AlertHubExtraction.init_extraction(
        metadata=AlertHubExtractionMetadata(
            params=AlertHubExtractionParamsMetadata(
                start=str(start_date),
                end=str(end_date),
                limit=0,  # NOTE: Parent extraction limit set to zero for extracting "count" for pagination.
                offset=0,
            ),
            url=f"{etl_config.ALERT_HUB_URL}/graphql/",
            type=AlertHubExtractionMetadataType.QUERY,
        ),
        queue_name=CeleryQueue.EXTRACTION,
    )
