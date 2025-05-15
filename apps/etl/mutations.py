import logging
from typing import List

import strawberry
from asgiref.sync import sync_to_async
from celery import chain

from apps.etl.extraction.sources.emdat.extract import EmdatExtraction
from apps.etl.extraction.sources.gidd.extract import GIDDExtraction
from apps.etl.extraction.sources.glide.extract import GlideExtraction
from apps.etl.extraction.sources.idu.extract import IDUExtraction
from apps.etl.extraction.sources.ifrc_event.extract import IFRCEventExtraction
from apps.etl.models import ExtractionData, Transform
from apps.etl.transform.sources.emdat import EMDATTransformHandler
from apps.etl.transform.sources.gidd import GIDDTransformHandler
from apps.etl.transform.sources.glide import GlideTransformHandler
from apps.etl.transform.sources.idu import IDUTransformHandler
from apps.etl.transform.sources.ifrc_event import IFRCEventTransformHandler
from main.graphql.context import Info

logger = logging.getLogger(__name__)

source_extraction_map = {
    ExtractionData.Source.EMDAT: EmdatExtraction,
    ExtractionData.Source.GLIDE: GlideExtraction,
    ExtractionData.Source.GIDD: GIDDExtraction,
    ExtractionData.Source.IDU: IDUExtraction,
    ExtractionData.Source.DREF: IFRCEventExtraction,
}
source_transform_map = {
    ExtractionData.Source.EMDAT: EMDATTransformHandler,
    ExtractionData.Source.GLIDE: GlideTransformHandler,
    ExtractionData.Source.GIDD: GIDDTransformHandler,
    ExtractionData.Source.IDU: IDUTransformHandler,
    ExtractionData.Source.DREF: IFRCEventTransformHandler,
}


@strawberry.input
class PipelineRetriggerInput:
    trace_id: List[int]


@strawberry.input
class TransformRetriggerInput:
    transform_id: List[int]


@strawberry.type
class Mutation:
    @strawberry.mutation
    async def retrigger_pipeline(
        self,
        data: PipelineRetriggerInput,  # type: ignore[reportInvalidTypeForm]
        info: Info,
    ) -> str:
        await sync_to_async(run_pipeline_retrigger)(data)
        return "Successfully retriggered pipeline"

    @strawberry.mutation
    async def retrigger_transform(
        self,
        data: TransformRetriggerInput,  # type: ignore[reportInvalidTypeForm]
        info: Info,
    ) -> str:
        await sync_to_async(run_transform_retrigger)(data)
        return "Successfully retriggered failed transform objects"


def run_transform_retrigger(data: TransformRetriggerInput) -> None:
    logger.info("Transform retrigger processing")
    failed_transform_objects = Transform.objects.filter(id__in=data.transform_id, status=Transform.Status.FAILED)

    for obj in failed_transform_objects:
        transform_class = source_transform_map[obj.extraction.source]
        transform_class.task.delay(obj.extraction.id)


def run_pipeline_retrigger(data: PipelineRetriggerInput) -> None:
    logger.info("Pipeline retrigger processing")

    failed_extraction_objects = ExtractionData.objects.filter(
        trace_id__in=data.trace_id, status=ExtractionData.Status.FAILED
    )
    for obj in failed_extraction_objects:
        extraction_class = source_extraction_map[obj.source]
        transform_class = source_transform_map[obj.source]
        if extraction_class == IFRCEventExtraction:
            extraction_class.task(obj.id)
        else:
            chain(extraction_class.task.s(obj.id), transform_class.task.s()).apply_async()
