from celery import shared_task
from django.conf import settings

from apps.etl.extraction.sources.usgs.extract import ext_and_transform_data


@shared_task
def ext_and_transform_usgs_latest_data():
    url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson"
    url = f"{settings.USGS_DATA_URL}/all_day.geojson"
    ext_and_transform_data.delay(url)


@shared_task
def ext_and_transform_usgs_historical_data():
    url = f"{settings.USGS_DATA_URL}/all_month.geojson"
    ext_and_transform_data.delay(url)
