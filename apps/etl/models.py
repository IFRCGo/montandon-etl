from apps.common.models import UserResource

# Create your models here.
from django.db import models
from django.utils.translation import gettext_lazy as _


class GDACS(UserResource):
    class Status(models.IntegerChoices):
        IN_PROGRESS = 1, _("In progress")
        PENDING = 2, _("Pending")
        SUCCESS = 3, _("Success")

    raw_data = models.JSONField(verbose_name=_("raw data"), default=dict)
    log = models.TextField(verbose_name=_("log"), blank=True)
    response_time = models.CharField(verbose_name=_("response time"), blank=True, max_length=100)
    response_code = models.IntegerField(verbose_name=_("response code"), blank=True)
    status = models.IntegerField(verbose_name=_("status"), choices=Status.choices)

    class Meta:
        verbose_name = _("gdac")
        verbose_name_plural = _("gdacs")
