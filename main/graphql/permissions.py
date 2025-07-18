from graphql import GraphQLError
from strawberry.extensions.field_extension import FieldExtension


class IsAuthenticated(FieldExtension):
    def resolve(self, _next, root, info, *args, **kwargs):
        user = info.context.request.user
        if not user.is_authenticated:
            raise GraphQLError("You must be logged in to access this resource.")
        return _next(root, info, *args, **kwargs)

    async def resolve_async(self, _next, root, info, *args, **kwargs):
        user = info.context.request.user
        if not user or not user.is_authenticated:
            raise GraphQLError("You must be logged in to access this resource.")
        return await _next(root, info, *args, **kwargs)
