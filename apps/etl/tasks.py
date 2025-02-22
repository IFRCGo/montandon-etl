from celery import shared_task
from django.core.management import call_command

from apps.etl.etl_tasks.desinventar import import_desinventar_data  # noqa: F401
from apps.etl.etl_tasks.emdat import extract_and_transform_emdat_data  # noqa: F401
from apps.etl.etl_tasks.gdacs import ext_and_transform_gdacs_data  # noqa: F401
from apps.etl.etl_tasks.glide import import_glide_hazard_data  # noqa: F401
from apps.etl.extraction.sources.gdacs.extract import (  # noqa: F401
    fetch_event_data,
    fetch_gdacs_geometry_data,
)
from apps.etl.extraction.sources.gfd.extract import GFDExtraction
from apps.etl.extraction.sources.gidd.extract import GIDDExtraction
from apps.etl.extraction.sources.glide.extract import (  # noqa: F401
    import_hazard_data as import_glide_data,
)
from apps.etl.extraction.sources.idu.extract import IDUExtraction
from apps.etl.extraction.sources.ifrc_event.extract import IFRCEventExtraction
from apps.etl.models import ExtractionData, HazardType  # noqa: F401
from apps.etl.transform.sources.gdacs import (  # noqa: F401
    transform_event_data,
    transform_geo_data,
    transform_impact_data,
)
from apps.etl.transform.sources.gfd import GFDTransformHandler  # noqa: F401
from apps.etl.transform.sources.gidd import GIDDTransformHandler  # noqa: F401
from apps.etl.transform.sources.glide import transform_glide_event_data  # noqa: F401
from apps.etl.transform.sources.handler import BaseTransformerHandler
from apps.etl.transform.sources.idu import IDUTransformHandler  # noqa: F401
from apps.etl.transform.sources.ifrc_event import (  # noqa: F401
    IFRCEventTransformHandler,
)

IDUExtraction.handle_extraction
GIDDExtraction.handle_extraction
GFDExtraction.handle_extraction
IFRCEventExtraction.handle_extraction

BaseTransformerHandler.handle_transformation


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
def extract_gidd_data():
    call_command("extract_gidd_data")


@shared_task
def extract_usgs_data():
    call_command("extract_usgs_data")


@shared_task
def extract_historical_data():
    call_command("extract_idu_data")
    call_command("extract_gfd_data")
    call_command("extract_ifrc_event_data.py")


@shared_task
def load_data():
    call_command("load_data_to_stac")
