from django.db import models


class Tracing(models.Model):
    trace_id = models.UUIDField(editable=False, default="00000000-0000-0000-0000-000000000000", db_index=True)

    class Meta:
        abstract = True


class Resource(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    # Typing
    id: int
    pk: int

    class Meta:
        abstract = True
