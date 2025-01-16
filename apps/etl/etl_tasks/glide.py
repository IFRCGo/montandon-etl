from celery import chain, shared_task
from django.core.management import call_command

from apps.etl.extraction.sources.glide.extract import (
    import_hazard_data as import_glide_data,
)
from apps.etl.transform.sources.glide import transform_glide_event_data
from apps.etl.load.sources.glide import load_glide_data


@shared_task
def import_glide_hazard_data(hazard_type: str, hazard_type_str: str, **kwargs):
    event_workflow = chain(
        import_glide_data.s(
            hazard_type=hazard_type,
            hazard_type_str=hazard_type_str,
        ),
        transform_glide_event_data.s(),
        load_glide_data.s(),
    )
    event_workflow.apply_async()

