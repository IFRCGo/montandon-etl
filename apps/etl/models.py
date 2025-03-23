# Create your models here.
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.common.models import Resource


class EtlTrace(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Trace"


class EtlResource(Resource):
    trace = models.ForeignKey(EtlTrace, null=True, related_name="+", on_delete=models.PROTECT)
    # types
    trace_id: int | None

    class Meta(Resource.Meta):
        abstract = True


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
# - Rename resp_text to resp_error
# - Rename resp_data_type to resp_content_type.
# - Remove resp_data_type
# - Remove url
# - Rename content_validation to validation_error
# - Remove hazard_type


# TODO:
# - Implement retries
# - Implement no_change optimization
# - Implement time tracking: started_at, completed_at
class ExtractionData(EtlResource):
    class Status(models.IntegerChoices):
        PENDING = 1, _("Pending")
        IN_PROGRESS = 2, _("In progress")
        SUCCESS = 3, _("Success")
        FAILED = 4, _("Failed")

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

    # METADATA
    source = models.IntegerField(verbose_name=_("source"), choices=Source.choices)
    # meta_data field contains data required for extraction and transformation
    metadata = models.JSONField(default=dict)
    parent = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="child_extractions")

    # STATUS
    status = models.IntegerField(verbose_name=_("status"), choices=Status.choices)
    source_validation_status = models.IntegerField(
        verbose_name=_("source data validation status"),
        choices=ValidationStatus.choices,
        default=ValidationStatus.NO_VALIDATION,
    )

    # CONTENT
    resp_code = models.IntegerField(verbose_name=_("HTTP response code"), blank=True)
    resp_data = models.FileField(verbose_name=_("Response data"), upload_to="source_raw_data/", blank=True, null=True)
    resp_type = models.IntegerField(verbose_name=_("Response type"), choices=ResponseDataType.choices, blank=True, null=True)

    # ERROR
    resp_text = models.TextField(verbose_name=_("Error message if request fails"), blank=True)
    content_validation = models.TextField(verbose_name=_("Error message if validation fails"), blank=True)

    # RETRIES
    attempt_no = models.IntegerField(verbose_name=_("Attempt number"), blank=True)

    # OPTIMIZATION
    file_hash = models.CharField(
        verbose_name=_("File hash value"),
        max_length=500,
        blank=True,
    )
    # This should point to the latest extraction with the same metadata if the file_hash matches
    # NOTE: We should define how the metadata is compared.
    revision_id = models.ForeignKey(
        "self",
        verbose_name=_("revision id"),
        help_text="This id points to the extraction object having same file content",
        on_delete=models.CASCADE,
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

    # FIXME: Add date range, Add country, Make hazard_type multiple selection
    # GOAL: We do not need to store URL but we need to store data that can be used to retrigger the data.

    def __str__(self):
        return str(self.id)


# TODO:
# - Implement time tracking: started_at, completed_at
# - Implement partial success and progress tracking: total_items, failed_items, completed_items
# - Rename to TransformData
# - Rename extraction to extraction_id to make this consistent with PyStacLoadData?
class Transform(EtlResource):
    class Status(models.IntegerChoices):
        PENDING = 1, "Pending"
        SUCCESS = 2, "Success"
        FAILED = 3, "Failed"
        # FIXME: We need to add PARTIAL_SUCCESS

    # METADATA
    extraction = models.ForeignKey(ExtractionData, on_delete=models.PROTECT, verbose_name=_("extraction"))

    # STATUS
    status = models.IntegerField(verbose_name=_("transform status"), choices=Status.choices)
    # FIXME: This might not be necessary
    is_loaded = models.BooleanField(
        default=False,
        help_text="Track whether transformer data has been successfully loaded into the PyStacLoadData table. This flag can be used to re-populate the data in case of any issues with the transformer.",  # noqa: E501
    )

    class Meta(EtlResource.Meta):
        verbose_name = "Transform"


# TODO:
# - Rename to LoadData
class PyStacLoadData(EtlResource):
    class ItemType(models.IntegerChoices):
        EVENT = 1, "Event"
        HAZARD = 2, "Hazard"
        IMPACT = 3, "Impact"

    class LoadStatus(models.IntegerChoices):
        PENDING = 1, "Pending"  # XXX: Value 1 is used in Meta.indexes
        SUCCESS = 2, "Success"
        FAILED = 3, "Failed"

    # METADATA
    transform_id = models.ForeignKey(Transform, on_delete=models.PROTECT, verbose_name=_("transform"))
    item_type = models.IntegerField(verbose_name=_("item type"), choices=ItemType.choices)
    collection_id = models.CharField(verbose_name=_("collection id"), max_length=250)  # FIXME: Use TextChoices

    # STATUS
    # FIXME: change to status
    load_status = models.IntegerField(verbose_name=_("load status"), choices=LoadStatus.choices, default=LoadStatus.PENDING)

    # CONTENT
    item = models.JSONField(verbose_name=_("item"), default=dict)

    class Meta(EtlResource.Meta):
        indexes = [
            models.Index(fields=["load_status"], name="partial_index_on_load_status", condition=models.Q(load_status=1)),
        ]
        verbose_name = "Stac Item"


def get_trace_id(parent_obj: ExtractionData | Transform | None) -> int | None:
    if parent_obj:
        return parent_obj.trace_id
    new_trace = EtlTrace.objects.create()
    return new_trace.pk
