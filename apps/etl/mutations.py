import strawberry
from asgiref.sync import sync_to_async

from apps.etl.serializers import RetriggerSerializer
from apps.etl.types import RetriggerResponse
from main.graphql.context import Info
from utils.strawberry.mutations import convert_serializer_to_type, process_input_data

RetriggerInput = convert_serializer_to_type(RetriggerSerializer, name="RetriggerInput")


@strawberry.type
class Mutation:
    @strawberry.mutation
    async def retrigger_content(
        self,
        data: RetriggerInput,  # type: ignore[reportInvalidTypeForm]
        info: Info,
    ) -> list[RetriggerResponse]:
        serializer = RetriggerSerializer(
            instance=info.context.request.user,
            data=process_input_data(data),
            context={"request": info.context.request},
        )
        # if errors := mutation_is_not_valid(serializer):
        #     return MutationResponseType(
        #         ok=False,
        #         errors=errors,
        #     )

        test = serializer.return_id()
        hero = await sync_to_async(list)(test)
        return [RetriggerResponse(id=test_id) async for test_id in hero]  # fix me
