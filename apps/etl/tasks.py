from celery import shared_task
from django.core.management import call_command

from apps.etl.etl_tasks.desinventar import import_desinventar_data  # noqa: F401
from apps.etl.etl_tasks.emdat import extract_and_transform_emdat_data  # noqa: F401
from apps.etl.etl_tasks.gdacs import import_hazard_data  # noqa: F401
from apps.etl.etl_tasks.glide import import_glide_hazard_data  # noqa: F401
from apps.etl.extraction.sources.gdacs.extract import (  # noqa: F401
    fetch_event_data,
    fetch_gdacs_geometry_data,
)
from apps.etl.extraction.sources.glide.extract import (  # noqa: F401
    import_hazard_data as import_glide_data,
)
from apps.etl.models import ExtractionData, HazardType  # noqa: F401
from apps.etl.transform.sources.gdacs import (  # noqa: F401
    transform_event_data,
    transform_geo_data,
    transform_impact_data,
)
from apps.etl.transform.sources.glide import transform_glide_event_data  # noqa: F401


@shared_task
def extract_gdacs_data():
    call_command("extract_gdacs_data")


@shared_task
def extract_glide_data():
    call_command("extract_glide_data")


@shared_task
def extract_desinventar_data():
    call_command("extract_desinventar_data")


@shared_task
def extract_emdat_data():
    call_command("extract_emdat_data")


@shared_task
def load_data():
    call_command("load_data_to_stac")
