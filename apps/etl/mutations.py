import logging
from typing import List
import strawberry
from typing import List
from asgiref.sync import sync_to_async

from apps.etl.serializers import RetriggerSerializer
from apps.etl.types import RetriggerResponse
from main.graphql.context import Info
from utils.strawberry.mutations import (
    convert_serializer_to_type,
    process_input_data,
    mutation_is_not_valid,
    MutationResponseType,
)

from apps.etl.models import Transform, ExtractionData
from apps.etl.extraction.sources.emdat.extract import EmdatExtraction
from apps.etl.extraction.sources.glide.extract import GlideExtraction
from apps.etl.extraction.sources.gidd.extract import GIDDExtraction
from apps.etl.extraction.sources.idu.extract import IDUExtraction
from apps.etl.extraction.sources.ifrc_event.extract import IFRCEventExtraction

from apps.etl.models import ExtractionData, Transform
from apps.etl.models import ExtractionData, Transform
from apps.etl.transform.sources.emdat import EMDATTransformHandler
from apps.etl.transform.sources.glide import GlideTransformHandler
from apps.etl.transform.sources.gidd import GIDDTransformHandler
from apps.etl.transform.sources.idu import IDUTransformHandler
from apps.etl.transform.sources.ifrc_event import IFRCEventTransformHandler

source_transformation_map = {
    ExtractionData.Source.EMDAT: EMDATTransformHandler,
    ExtractionData.Source.GLIDE: GlideTransformHandler,
    ExtractionData.Source.GIDD: GIDDTransformHandler,
    ExtractionData.Source.IDU: IDUTransformHandler,
    ExtractionData.Source.DREF: IFRCEventTransformHandler,
}
source_extraction_map = {
    ExtractionData.Source.EMDAT: EmdatExtraction,
    ExtractionData.Source.GLIDE: GlideExtraction,
    ExtractionData.Source.GIDD: GIDDExtraction,
    ExtractionData.Source.IDU: IDUExtraction,
    ExtractionData.Source.DREF: IFRCEventExtraction,

}

@strawberry.input
class RetriggerInput:
    trace_id: int

@strawberry.type
class Mutation:
    @strawberry.mutation
    @sync_to_async
    def retrigger_content(
        self,
        data: RetriggerInput,  # type: ignore[reportInvalidTypeForm]
        info: Info,
    ) -> List[RetriggerResponse]:
    # ) -> str:

        # failed_transformation_objects = Transform.objects.filter(trace_id=data.trace_id)
        failed_transformation_objects = Transform.objects.filter(id=845252)

        status_list = []
        for obj in failed_transformation_objects:
            transform_class = source_transformation_map[obj.extraction.source]
            result = transform_class.task.delay(obj.extraction.id)
            print("REsult", result)
            print("Type REsult", type(result))
            status_list.append(result.status)


        # failed_extraction_objects = ExtractionData.objects.filter(trace_id=data.trace_id)
        # print("failed_extraction_objects", failed_extraction_objects)

        # for obj in failed_extraction_objects:
        #     extraction_class = source_extraction_map[obj.source]
        #     extraction_class.task(obj.id)

        return [RetriggerResponse(trace_id=data.trace_id, status=result.status) for result in status_list]
        # return "Retriggered Successfully" # fix me
