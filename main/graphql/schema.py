import strawberry
from strawberry.django.views import AsyncGraphQLView

from apps.etl import queries as etl_queries

from .context import GraphQLContext
from .dataloaders import GlobalDataLoader
from main.graphql.enums import AppEnumCollection, AppEnumCollectionData
from .permissions import IsAuthenticated


class CustomAsyncGraphQLView(AsyncGraphQLView):
    async def get_context(self, *args, **kwargs) -> GraphQLContext:
        return GraphQLContext(
            *args,
            **kwargs,
            dl=GlobalDataLoader(),
        )


@strawberry.type
class PublicQuery(
    etl_queries.PublicQuery,
):
    id: strawberry.ID = strawberry.ID('public')


@strawberry.type
class PrivateQuery(
   
):
    id: strawberry.ID = strawberry.ID('private')


@strawberry.type
class PublicMutation(
   
):
    id: strawberry.ID = strawberry.ID('public')


@strawberry.type
class PrivateMutation(
   
):
    id: strawberry.ID = strawberry.ID('private')


@strawberry.type
class Query:
    public: PublicQuery = strawberry.field(resolver=lambda: PublicQuery())
    private: PrivateQuery = strawberry.field(permission_classes=[IsAuthenticated], resolver=lambda: PrivateQuery())
    enums: AppEnumCollection = strawberry.field(  # type: ignore[reportGeneralTypeIssues]
        resolver=lambda: AppEnumCollectionData()
    )


@strawberry.type
class Mutation:
    public: PublicMutation = strawberry.field(resolver=lambda: PublicMutation())
    private: PrivateMutation = strawberry.field(
        resolver=lambda: PrivateMutation(),
        permission_classes=[IsAuthenticated],
    )


schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
)
