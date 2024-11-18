# Create your models here.
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.common.models import UserResource


class ExtractionLog(UserResource):
    class Source(models.IntegerChoices):
        GDACS = 1, _("Gdacs")
        PDC = 2, _("pdc")

    class Status(models.IntegerChoices):
        PENDING = 1, _("Pending")
        IN_PROGRESS = 2, _("In progress")
        SUCCESS = 3, _("Success")
        FAILED = 4, _("Failed")

    uuid = models.UUIDField()
    source = models.IntegerField(verbose_name=_("source"), choices=Source.choices)
    url = models.URLField(blank=True)
    attempt_no = models.IntegerField(blank=True)
    req_started_datetime = models.DateTimeField(blank=True)
    response_time = models.TimeField(blank=True)
    response_code = models.IntegerField(verbose_name=_("response code"), blank=True)
    status = models.IntegerField(verbose_name=_("status"), choices=Status.choices)


class ExtractionData(UserResource):
    class ResponseDataType(models.IntegerChoices):
        JSON = 1, _("Json")
        CSV = 2, _("CSV")
        TEXT = 3, _("Text")

    extraction_log = models.ForeignKey(ExtractionLog, on_delete=models.CASCADE, related_name="extraction_log")
    uuid = models.UUIDField()
    raw_data = models.TextField(verbose_name=_("raw data"), blank=True)
    response_data_type = models.IntegerField(choices=ResponseDataType.choices)
