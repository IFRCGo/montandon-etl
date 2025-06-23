import logging

import strawberry
from asgiref.sync import sync_to_async

from apps.etl.extraction.sources.desinventar.extract import DesInventarExtraction
from apps.etl.extraction.sources.emdat.extract import EmdatExtraction
from apps.etl.extraction.sources.gdacs.extract import GdacsExtraction
from apps.etl.extraction.sources.gfd.extract import GFDExtraction
from apps.etl.extraction.sources.gidd.extract import GIDDExtraction
from apps.etl.extraction.sources.glide.extract import GlideExtraction
from apps.etl.extraction.sources.idu.extract import IDUExtraction
from apps.etl.extraction.sources.ifrc_event.extract import IFRCEventExtraction
from apps.etl.extraction.sources.noaa_IBTrACS.extract import IBTrACSExtraction
from apps.etl.extraction.sources.pdc.extract import PDCExtractionV2
from apps.etl.extraction.sources.usgs.extract import USGSExtraction
from apps.etl.input_types import PipelineRetriggerInput, TransformRetriggerInput
from apps.etl.models import ExtractionData, Transform
from apps.etl.transform.sources.desinventar import DesinventarTransformHandler
from apps.etl.transform.sources.emdat import EMDATTransformHandler
from apps.etl.transform.sources.gdacs import GDACSTransformHandler
from apps.etl.transform.sources.gfd import GFDTransformHandler
from apps.etl.transform.sources.gidd import GIDDTransformHandler
from apps.etl.transform.sources.glide import GlideTransformHandler
from apps.etl.transform.sources.idu import IDUTransformHandler
from apps.etl.transform.sources.ifrc_event import IFRCEventTransformHandler
from apps.etl.transform.sources.noaa_ibtracs import IbtracsTransformHandler
from apps.etl.transform.sources.pdc import PDCTransformHandler
from apps.etl.transform.sources.usgs import USGSTransformHandler
from main.graphql.context import Info
from utils.strawberry.mutations import MutationResponseType, _CustomErrorType

logger = logging.getLogger(__name__)

source_extraction_map = {
    ExtractionData.Source.EMDAT: EmdatExtraction,
    ExtractionData.Source.GLIDE: GlideExtraction,
    ExtractionData.Source.GIDD: GIDDExtraction,
    ExtractionData.Source.IDU: IDUExtraction,
    ExtractionData.Source.DREF: IFRCEventExtraction,
    ExtractionData.Source.DESINVENTAR: DesInventarExtraction,
    ExtractionData.Source.GFD: GFDExtraction,
    ExtractionData.Source.GDACS: GdacsExtraction,
    ExtractionData.Source.USGS: USGSExtraction,
    ExtractionData.Source.PDC: PDCExtractionV2,
    ExtractionData.Source.IBTRACS: IBTrACSExtraction,
}
source_transform_map = {
    ExtractionData.Source.EMDAT: EMDATTransformHandler,
    ExtractionData.Source.GLIDE: GlideTransformHandler,
    ExtractionData.Source.GIDD: GIDDTransformHandler,
    ExtractionData.Source.IDU: IDUTransformHandler,
    ExtractionData.Source.DREF: IFRCEventTransformHandler,
    ExtractionData.Source.GDACS: GDACSTransformHandler,
    ExtractionData.Source.DESINVENTAR: DesinventarTransformHandler,
    ExtractionData.Source.GFD: GFDTransformHandler,
    ExtractionData.Source.IBTRACS: IbtracsTransformHandler,
    ExtractionData.Source.PDC: PDCTransformHandler,
    ExtractionData.Source.USGS: USGSTransformHandler,
}


@strawberry.type
class Mutation:
    @strawberry.mutation
    async def retrigger_pipeline(
        self,
        data: PipelineRetriggerInput,
        info: Info,
    ) -> MutationResponseType[str]:
        try:
            await sync_to_async(run_pipeline_retrigger)(data)
            return MutationResponseType(ok=True, result="Successfully retriggered pipeline")
        except Exception:
            return MutationResponseType(
                ok=False,
                errors=_CustomErrorType.generate_message("Fail to retrigger pipeline"),
            )

    @strawberry.mutation
    async def retrigger_transform(
        self,
        data: TransformRetriggerInput,
        info: Info,
    ) -> MutationResponseType[str]:
        try:
            await sync_to_async(run_transform_retrigger)(data)
            return MutationResponseType(ok=True, result="Successfully retriggered failed transform objects")
        except Exception:
            return MutationResponseType(
                ok=False,
                errors=_CustomErrorType.generate_message("Fail to retrigger failed transform objects"),
            )


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
        # during the retrigger process some to the failed_extraction_objects are retriggered internally
        # so lets not retrigger those objects
        if obj.status == ExtractionData.Status.SUCCESS:
            continue
        extraction_class = source_extraction_map[obj.source]
        if extraction_class in [GdacsExtraction, USGSExtraction, PDCExtractionV2]:  # nested extraction
            extraction_class.retrigger(obj)
        else:
            extraction_class.task.delay(obj.id)
