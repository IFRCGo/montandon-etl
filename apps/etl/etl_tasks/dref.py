from celery import chain, shared_task

from apps.etl.extraction.sources.dref.extract import DREFExtraction
# from apps.etl.transform.sources.dref import DREFTransformHandler


@shared_task
def ext_and_transform_dref_data():
    return DREFExtraction.task()
    # chain(
    #     DREFExtraction.task.s(),
    #     DREFTransformHandler.task.s(),
    # ).apply_async()
