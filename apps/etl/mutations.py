import logging
from typing import List

import strawberry
from asgiref.sync import sync_to_async
from celery import chain, chord, group, shared_task

from apps.etl.extraction.sources.cems.extract import CEMSExtraction
from apps.etl.extraction.sources.desinventar.extract import DesInventarExtraction
from apps.etl.extraction.sources.disaster_charter.extract import CharterExtraction
from apps.etl.extraction.sources.emdat.extract import EmdatExtraction
from apps.etl.extraction.sources.gdacs.extract import GdacsExtraction
from apps.etl.extraction.sources.gfd.extract import GFDExtraction
from apps.etl.extraction.sources.gidd.extract import GIDDExtraction
from apps.etl.extraction.sources.glide.extract import GlideExtraction
from apps.etl.extraction.sources.idu.extract import IDUExtraction
from apps.etl.extraction.sources.ifrc_event.extract import IFRCEventExtractionV2
from apps.etl.extraction.sources.noaa_IBTrACS.extract import IBTrACSExtraction
from apps.etl.extraction.sources.pdc.extract import PDCExtractionMetaDataType, PDCExtractionV2
from apps.etl.extraction.sources.usgs.extract import USGSExtraction
from apps.etl.input_types import PipelineRetriggerInput, TransformRetriggerInput
from apps.etl.models import ExtractionData, Transform
from apps.etl.transform.sources.cems import CEMSTransformHandler
from apps.etl.transform.sources.desinventar import DesinventarTransformHandler
from apps.etl.transform.sources.disaster_charter import DisasterCharterTransformHandler
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
from apps.etl.types import PipelineRetriggerType
from utils.strawberry.mutations import MutationResponseType, _CustomErrorType

logger = logging.getLogger(__name__)

source_extraction_map = {
    ExtractionData.Source.EMDAT: EmdatExtraction,
    ExtractionData.Source.GLIDE: GlideExtraction,
    ExtractionData.Source.GIDD: GIDDExtraction,
    ExtractionData.Source.IDU: IDUExtraction,
    ExtractionData.Source.DREF: IFRCEventExtractionV2,
    ExtractionData.Source.DESINVENTAR: DesInventarExtraction,
    ExtractionData.Source.GFD: GFDExtraction,
    ExtractionData.Source.GDACS: GdacsExtraction,
    ExtractionData.Source.USGS: USGSExtraction,
    ExtractionData.Source.PDC: PDCExtractionV2,
    ExtractionData.Source.IBTRACS: IBTrACSExtraction,
    ExtractionData.Source.DISASTERCHARTER: CharterExtraction,
    ExtractionData.Source.CEMS: CEMSExtraction,
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
    ExtractionData.Source.DISASTERCHARTER: DisasterCharterTransformHandler,
    ExtractionData.Source.CEMS: CEMSTransformHandler,
}


def validate_retrigger_transform(data: TransformRetriggerInput) -> List[int]:
    failed_transform_objects = Transform.objects.filter(id__in=data.transform_ids, status=Transform.Status.FAILED)

    if not failed_transform_objects.exists():
        raise ValueError("No failed transform objects found for the provided IDs")

    existing_ids = set(Transform.objects.filter(id__in=data.transform_ids).values_list("id", flat=True).distinct())

    missing_ids = set(data.transform_ids) - set(str(id) for id in existing_ids)
    if missing_ids:
        raise ValueError(f"IDs not found: {', '.join(missing_ids)}")

    return [obj.id for obj in failed_transform_objects]


def validate_retrigger_pipeline(data: PipelineRetriggerInput) -> List[int]:
    failed_extraction_objects = ExtractionData.objects.filter(
        trace_id__in=data.trace_ids, status=ExtractionData.Status.FAILED
    )
    if not failed_extraction_objects.exists():
        raise ValueError("No failed extraction objects found for the provided trace IDs")

    existing_trace_ids = set(
        ExtractionData.objects.filter(trace_id__in=data.trace_ids).values_list("trace_id", flat=True).distinct()
    )

    missing_trace_ids = set(data.trace_ids) - set(str(id) for id in existing_trace_ids)
    if missing_trace_ids:
        raise ValueError(f"Trace IDs not found: {', '.join(missing_trace_ids)}")

    return [obj.id for obj in failed_extraction_objects]


@shared_task
def run_transform_retrigger(transform_objects_ids: List[int]) -> None:
    logger.info("Transform retrigger processing")

    failed_transform_objects = Transform.objects.filter(
        id__in=transform_objects_ids,
    )
    if failed_transform_objects.exists():
        failed_transform_objects.update(status=Transform.Status.PENDING)
        for obj in failed_transform_objects:
            transform_class = source_transform_map[obj.extraction.source]
            transform_class.task.delay(obj.extraction.id)


@shared_task
def trigger_pdc_transform(trace_ids: List[int]):
    """Collect the failed items from the Transform table"""
    success_ext_detail_ids = ExtractionData.objects.filter(
        metadata__type="EXPOSURE_DETAIL",
        status=ExtractionData.Status.SUCCESS,
        source=ExtractionData.Source.PDC,
    ).values("id")

    failed_transform_objs = Transform.objects.filter(
        extraction__id__in=success_ext_detail_ids, status=Transform.Status.FAILED, trace__id__in=trace_ids
    )
    run_transform_retrigger.delay(list(failed_transform_objs.values_list("id", flat=True)))


@shared_task
def run_pipeline_retrigger(extraction_objects_ids: List[int]) -> None:
    logger.info("Pipeline retrigger processing")

    pdc_failed_objects = ExtractionData.objects.filter(id__in=extraction_objects_ids, source=ExtractionData.Source.PDC)

    failed_extraction_objects = ExtractionData.objects.filter(id__in=extraction_objects_ids).exclude(
        id__in=pdc_failed_objects
    )
    if failed_extraction_objects.exists():
        for obj in failed_extraction_objects:
            # during the retrigger process some to the failed_extraction_objects are retriggered internally
            # so lets not retrigger those objects
            if obj.status == ExtractionData.Status.SUCCESS:
                continue
            obj.status = ExtractionData.Status.PENDING
            obj.save(update_fields=["status"])

            extraction_class = source_extraction_map[obj.source]
            if extraction_class in [GdacsExtraction, USGSExtraction]:  # nested extraction
                extraction_class.retrigger(obj)
            else:
                extraction_class.task.delay(obj.id)

    # Retrigger PDC
    if pdc_failed_objects:
        pdc_hazard_objects = pdc_failed_objects.filter(metadata__type=PDCExtractionMetaDataType.HAZARD)
        pdc_polygon_objects = pdc_failed_objects.filter(metadata__type=PDCExtractionMetaDataType.POLYGON)
        pdc_list_objects = pdc_failed_objects.filter(metadata__type=PDCExtractionMetaDataType.EXPOSURE_LIST)
        pdc_detail_objects = pdc_failed_objects.filter(metadata__type=PDCExtractionMetaDataType.EXPOSURE_DETAIL)

        trace_ids = list(
            set(pdc_hazard_objects.values_list("trace", flat=True))
            | set(pdc_polygon_objects.values_list("trace", flat=True))
            | set(pdc_list_objects.values_list("trace", flat=True))
            | set(pdc_detail_objects.values_list("trace", flat=True))
        )
        pdc_hazard_objects = [PDCExtractionV2.task.si(obj.id) for obj in pdc_hazard_objects]
        polygon_tasks = [PDCExtractionV2.task.si(obj.id) for obj in pdc_polygon_objects]
        list_tasks = [PDCExtractionV2.task.si(obj.id) for obj in pdc_list_objects]
        detail_tasks = [PDCExtractionV2.task.si(obj.id) for obj in pdc_detail_objects]

        pdc_retrigger_workflow = chord(
            pdc_hazard_objects,
            chain(group(polygon_tasks), group(list_tasks), group(detail_tasks), trigger_pdc_transform.si(trace_ids)),
        )
        pdc_retrigger_workflow.apply_async()


@strawberry.type
class Mutation:
    @strawberry.mutation
    async def retrigger_pipeline(
        self,
        data: PipelineRetriggerInput,
    ) -> MutationResponseType[PipelineRetriggerType]:
        try:
            failed_extraction_objects_ids = await sync_to_async(validate_retrigger_pipeline)(data)
            task_id = run_pipeline_retrigger.delay(failed_extraction_objects_ids)
            return MutationResponseType(ok=True, result=PipelineRetriggerType(task_id=task_id, status=task_id.status))
        except ValueError as e:
            return MutationResponseType(
                ok=False,
                errors=_CustomErrorType.generate_message(str(e)),
            )
        except Exception:
            return MutationResponseType(
                ok=False,
                errors=_CustomErrorType.generate_message("Fail to retrigger pipeline"),
            )

    @strawberry.mutation
    async def retrigger_transform(
        self,
        data: TransformRetriggerInput,
    ) -> MutationResponseType[PipelineRetriggerType]:
        try:
            failed_transform_objects_ids = await sync_to_async(validate_retrigger_transform)(data)
            task_id = run_transform_retrigger.delay(failed_transform_objects_ids)
            return MutationResponseType(ok=True, result=PipelineRetriggerType(task_id=task_id, status=task_id.status))
        except ValueError as e:
            return MutationResponseType(
                ok=False,
                errors=_CustomErrorType.generate_message(str(e)),
            )
        except Exception:
            return MutationResponseType(
                ok=False,
                errors=_CustomErrorType.generate_message("Fail to retrigger failed transform objects"),
            )
