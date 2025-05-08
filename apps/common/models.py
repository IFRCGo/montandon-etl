from django.db import models

# from apps.user.models import User


class Resource(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    # Typing
    id: int

    class Meta:
        abstract = True
        ordering = ["-id"]


# class UserResource(models.Model):
#     created_at = models.DateTimeField(auto_now_add=True)
#     modified_at = models.DateTimeField(auto_now=True)
#     created_by = models.ForeignKey(
#         User,
#         related_name="%(class)s_created",
#         on_delete=models.PROTECT,
#     )
#     modified_by = models.ForeignKey(
#         User,
#         related_name="%(class)s_modified",
#         on_delete=models.PROTECT,
#     )

#     # Typing
#     created_by_id: int
#     modified_by_id: int

#     class Meta:  # type: ignore[reportIncompatibleVariableOverride]
#         abstract: bool = True
#         ordering: list[str] = ["-id"]

#     @typing.override
#     def __str__(self):
#         return str(self.pk)
