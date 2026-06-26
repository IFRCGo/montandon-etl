import typing

from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import GinIndex
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.common.models import Resource


class EtlTrace(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Trace"

    def __str__(self):
        return str(self.pk)


class Status(models.IntegerChoices):
    PENDING = 1, _("Pending")
    IN_PROGRESS = 2, _("In progress")
    SUCCESS = 3, _("Success")
    FAILED = 4, _("Failed")
    ON_RETRY = 5, _("On Retry")


class EtlTraceResource(models.Model):
    trace = models.ForeignKey(EtlTrace, related_name="+", on_delete=models.PROTECT)
    # types
    trace_id: int

    class Meta:
        abstract = True

    def __str__(self):
        return str(self.pk)


class EtlResource(Resource, EtlTraceResource):
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    status = models.IntegerField(verbose_name=_("status"), choices=Status.choices, default=Status.PENDING)

    class Meta(Resource.Meta, EtlTraceResource.Meta):
        abstract = True

    def mark_as_started(self):
        self.status = Status.IN_PROGRESS
        self.started_at = timezone.now()
        self.save(update_fields=["status", "started_at"])

    def mark_as_ended(
        self,
        status: typing.Literal[Status.FAILED, Status.SUCCESS, Status.ON_RETRY],
        *,
        update_fields: list[str] = [],
    ):
        self.status = status
        self.ended_at = timezone.now()
        self.save(update_fields=["status", "ended_at", *update_fields])

    def __str__(self):
        return str(self.id)


# TODO: Use IntegerChoices and add mapping for import/export
class HazardType(models.TextChoices):
    EARTHQUAKE = "EQ", "Earthquake"
    FLOOD = "FL", "Flood"
    CYCLONE = "TC", "Cyclone"
    EPIDEMIC = "EP", "Epidemic"
    FOOD_INSECURITY = "FI", "Food Insecurity"
    STORM = "SS", "Storm Surge"
    DROUGHT = "DR", "Drought"
    TSUNAMI = "TS", "Tsunami"
    WIND = "CD", "Cyclonic Wind"
    WILDFIRE = "WF", "WildFire"
    VOLCANO = "VO", "Volcano"
    COLDWAVE = "CW", "Cold Wave"
    COMPLEX_EMERGENCY = "CE", "Complex Emergency"
    EXTRATROPICAL_CYCLONE = "EC", "Extratropical Cyclone"
    EXTREME_TEMPERATURE = "ET", "Extreme temperature"
    FAMINE = "FA", "Famine"
    FIRE = "FR", "Fire"
    FLASH_FLOOD = "FF", "Flash Flood"
    HEAT_WAVE = "HT", "Heat Wave"
    INSECT_INFESTATION = "IN", "Insect Infestation"
    LANDSLIDE = "LS", "Land Slide"
    MUD_SLIDE = "MS", "Mud Slide"
    SEVERE_LOCAL_STROM = "ST", "Severe Local Strom"
    SLIDE = "SL", "Slide"
    SNOW_AVALANCHE = "AV", "Snow Avalanche"
    TECH_DISASTER = "AC", "Tech. Disaster"
    TORNADO = "TO", "Tornado"
    VIOLENT_WIND = "VW", "Violent Wind"
    WAVE_SURGE = "WV", "Wave/Surge"
    OTHER = "OT", "Other"


# FIXME:
# - Rename source_validation_status to validation_status
# - Rename resp_data_type to resp_content_type.
# - Remove resp_data_type
# - Remove url
# - Remove hazard_type


def extract_data_upload_to(instance: "ExtractionData", filename: str):
    today = timezone.now().strftime("%Y-%m-%d")
    if instance.source in ExtractionData.Source:
        source_label = ExtractionData.Source(instance.source).name.lower()
    else:
        # Fallback
        source_label = instance.source
    return f"extract-raw-data/source-{source_label}/{today}/{filename}"


# TODO:
# - Implement retries
# - Implement no_change optimization
# - Implement time tracking: started_at, completed_at
class ExtractionData(EtlResource):
    Status = Status

    class ValidationStatus(models.IntegerChoices):
        SUCCESS = 1, _("Success")
        FAILED = 2, _("Failed")
        NO_DATA = 3, _("No data")
        NO_CHANGE = 4, _("No change")
        NO_VALIDATION = 5, _("No validation")

    class ResponseDataType(models.IntegerChoices):
        JSON = 1, _("json")
        CSV = 2, _("csv")
        TEXT = 3, _("text")
        HTML = 4, _("html")
        XML = 5, _("xml")
        PDF = 6, _("pdf")

    class Source(models.IntegerChoices):
        GDACS = 1, _("GDACS")
        PDC = 2, _("PDC")
        GLIDE = 3, _("Glide")
        IBTRACS = 4, _("NOAA-IBTrACS")
        EMDAT = 5, _("EM-DAT")
        GIDD = 6, _("IDMC-GIDD")
        IDU = 7, _("IDMC-IDU")
        USGS = 8, _("USGS Shakesmaps")
        GFD = 9, _("Global Flood Database")
        DFO = 10, _("DFO")
        STORM = 11, _("STORM")
        DREF = 12, _("IFRC DREF & EA")
        WFPADAM = 13, _("WFP-ADAM")
        DESINVENTAR = 14, _("DesInventar")
        DISASTERCHARTER = 15, _("DisasterCharter")
        CEMS = 16, _("CEMS")

    # METADATA
    source = models.IntegerField(verbose_name=_("source"), choices=Source.choices, db_index=True)
    # meta_data field contains data required for extraction and transformation
    metadata = models.JSONField(default=dict)
    parent = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="child_extractions")

    # STATUS
    source_validation_status = models.IntegerField(
        verbose_name=_("source data validation status"),
        choices=ValidationStatus.choices,
        default=ValidationStatus.NO_VALIDATION,
    )

    # CONTENT
    resp_code = models.IntegerField(verbose_name=_("HTTP response code"), null=True, blank=True)
    resp_data = models.FileField(verbose_name=_("Response data"), upload_to=extract_data_upload_to, blank=True, null=True)
    resp_type = models.IntegerField(verbose_name=_("Response type"), choices=ResponseDataType.choices, blank=True, null=True)

    # RETRIES
    attempt_no = models.IntegerField(verbose_name=_("Attempt number"), blank=True)

    # OPTIMIZATION
    file_hash = models.CharField(verbose_name=_("File hash value"), max_length=500, blank=True, null=True)
    # This should point to the latest extraction with the same metadata if the file_hash matches
    # TODO: We should define how the metadata is compared.
    revision_id = models.ForeignKey(
        "self",
        verbose_name=_("revision id"),
        help_text="This id points to the extraction object having same file content",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )

    # OBSOLETE

    resp_data_type = models.CharField(verbose_name=_("Response data type"), blank=True)
    url = models.URLField(verbose_name=_("url"), blank=True)
    hazard_type = models.CharField(
        max_length=100, verbose_name=_("hazard type"), choices=HazardType.choices, blank=True, null=True
    )

    class Meta(EtlResource.Meta):
        verbose_name = "Extraction"

    # TODO: We do not need to store URL but we need to store data that can be used to retrigger the data.


# TODO:
# - Implement time tracking: started_at, completed_at
# - Implement partial success and progress tracking: total_items, failed_items, completed_items
# - Rename to TransformData
# - Rename extraction to extraction_id to make this consistent with PyStacLoadData?
class Transform(EtlResource):
    Status = Status

    # METADATA
    version = models.CharField(max_length=10, default="1.0.0")
    metadata = models.JSONField(default=dict)
    extraction = models.ForeignKey(ExtractionData, on_delete=models.PROTECT, verbose_name=_("extraction"))

    class Meta(EtlResource.Meta):
        verbose_name = "Transform"

    def __str__(self):
        return str(self.id)


# TODO:
# - Use partial table index for collection_id
class PyStacLoadData(EtlTraceResource, Resource):
    class Status(models.IntegerChoices):
        PENDING = 1, _("Pending")
        # IN_PROGRESS = 2, _("In progress")
        SUCCESS = 3, _("Success")
        FAILED = 4, _("Failed")

    class ItemType(models.IntegerChoices):
        EVENT = 1, "Event"
        HAZARD = 2, "Hazard"
        IMPACT = 3, "Impact"
        RESPONSE = 4, "Response"

    # METADATA
    transform_id = models.ForeignKey(Transform, on_delete=models.PROTECT, verbose_name=_("transform"))
    item_type = models.IntegerField(verbose_name=_("item type"), choices=ItemType.choices, db_index=True)
    collection_id = models.CharField(
        verbose_name=_("collection id"), max_length=250, db_index=True
    )  # FIXME: Use TextChoices

    # CONTENT
    item = models.JSONField(verbose_name=_("item"), default=dict)

    # Custom indexed fields for Aggregation
    item_id = models.CharField(
        verbose_name="item Id",
        max_length=150,
        db_index=True,
        null=True,
    )
    item_datetime = models.DateTimeField(
        verbose_name="item datetime",
        db_index=True,
        null=True,
    )
    item_primary_country = ArrayField(models.CharField(max_length=150), null=True)

    status = models.IntegerField(verbose_name=_("status"), choices=Status.choices, default=Status.PENDING)

    class Meta(EtlTraceResource.Meta, Resource.Meta):
        indexes = [
            models.Index(
                fields=["status"], name="loaddata_pi_status_pending", condition=models.Q(status=Status.PENDING.value)
            ),
            GinIndex(fields=["item_primary_country"]),  # GinIndex for ArrayField
            models.Index(fields=["item_id", "item_type"]),
        ]
        verbose_name = "Stac Item"


def get_trace_id(parent_obj: ExtractionData | Transform | None) -> int | None:
    if parent_obj:
        return parent_obj.trace_id

    new_trace = EtlTrace.objects.create()
    return new_trace.pk
