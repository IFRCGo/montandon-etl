import strawberry
from strawberry.django.views import AsyncGraphQLView
from strawberry_django.optimizer import DjangoOptimizerExtension

from apps.etl import mutations as etl_mutations
from apps.etl import queries as etl_queries
from apps.user import mutations as user_mutations
from apps.user import queries as user_queries
from main.graphql.enums import AppEnumCollection, AppEnumCollectionData

from .context import GraphQLContext
from .dataloaders import GlobalDataLoader


class CustomAsyncGraphQLView(AsyncGraphQLView):
    async def get_context(self, *args, **kwargs) -> GraphQLContext:
        return GraphQLContext(
            *args,
            **kwargs,
            dl=GlobalDataLoader(),
        )


@strawberry.type
class Query(etl_queries.Query, user_queries.Query):
    enums: AppEnumCollection = strawberry.field(  # type: ignore[reportGeneralTypeIssues]
        resolver=lambda: AppEnumCollectionData(),
    )


@strawberry.type
class Mutation(
    user_mutations.Mutation,
    etl_mutations.Mutation,
): ...


schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    extensions=[
        DjangoOptimizerExtension,
    ],
)
