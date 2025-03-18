from celery import shared_task
from django.core.management import call_command

from apps.etl.etl_tasks.emdat import (  # noqa: F401
    ext_and_transform_emdat_historical_data,
    ext_and_transform_emdat_latest_data,
)
from apps.etl.etl_tasks.gdacs import (  # noqa: F401
    ext_and_transform_gdacs_data,
    ext_and_transform_gdacs_latest_data,
)
from apps.etl.etl_tasks.gfd import ext_and_transform_gfd_latest_data  # noqa: F401
from apps.etl.etl_tasks.glide import (  # noqa: F401
    ext_and_transform_data,
    ext_and_transform_glide_latest_data,
)
from apps.etl.etl_tasks.idu import (  # noqa: F401
    ext_and_transform_idu_historical_data,
    ext_and_transform_idu_latest_data,
)
from apps.etl.etl_tasks.ifrc_event import (  # noqa: F401
    ext_and_transform_ifrcevent_historical_data,
    ext_and_transform_ifrcevent_latest_data,
)
from apps.etl.etl_tasks.pdc import extract_and_transform_pdc_data  # noqa: F401
from apps.etl.etl_tasks.usgs import (  # noqa: F401
    ext_and_transform_usgs_historical_data,
    ext_and_transform_usgs_latest_data,
)
from apps.etl.extraction.sources.desinventar.extract import DesinventarExtraction
from apps.etl.extraction.sources.gdacs.extract import (  # noqa: F401
    fetch_event_data,
    fetch_gdacs_geometry_data,
)
from apps.etl.extraction.sources.gfd.extract import GFDExtraction
from apps.etl.extraction.sources.gidd.extract import GIDDExtraction
from apps.etl.extraction.sources.glide.extract import (  # noqa: F401
    import_glide_hazard_data,
)
from apps.etl.extraction.sources.idu.extract import IDUExtraction
from apps.etl.extraction.sources.ifrc_event.extract import IFRCEventExtraction
from apps.etl.models import ExtractionData, HazardType  # noqa: F401
from apps.etl.transform.sources.desinventar import (  # noqa: F401
    DesinventarTransformHandler,
)
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
DesinventarExtraction.handle_extraction
GIDDExtraction.handle_extraction
GFDExtraction.handle_extraction
IFRCEventExtraction.handle_extraction

BaseTransformerHandler.handle_transformation


@shared_task
def extract_pdc_data():
    call_command("extract_pdc_data")


@shared_task
def extract_gidd_data():
    call_command("extract_gidd_data")


@shared_task
def extract_usgs_data():
    call_command("extract_usgs_data")


@shared_task
def load_data():
    call_command("load_data_to_stac")
