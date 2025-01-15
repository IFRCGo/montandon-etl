from django.db import models
from django.utils.translation import gettext_lazy as _


class UserResource(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    # Typing
    id: int
    pk: int

    class Meta:
        abstract = True
        ordering = ["-id"]
