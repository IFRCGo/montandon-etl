# Create your models here.
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.common.models import UserResource


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


class ExtractionData(UserResource):
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

    class Status(models.IntegerChoices):
        PENDING = 1, _("Pending")
        IN_PROGRESS = 2, _("In progress")
        SUCCESS = 3, _("Success")
        FAILED = 4, _("Failed")

    source = models.IntegerField(verbose_name=_("source"), choices=Source.choices)
    url = models.URLField(verbose_name=_("url"), blank=True)
    attempt_no = models.IntegerField(verbose_name=_("attempt number"), blank=True)
    resp_code = models.IntegerField(verbose_name=_("response code"), blank=True)
    status = models.IntegerField(verbose_name=_("status"), choices=Status.choices)
    resp_data = models.FileField(verbose_name=_("response data"), upload_to="source_raw_data/", blank=True, null=True)
    file_hash = models.CharField(
        verbose_name=_("file hash value"),
        max_length=500,
        blank=True,
    )
    resp_type = models.IntegerField(verbose_name=_("response type"), choices=ResponseDataType.choices, blank=True, null=True)
    resp_data_type = models.CharField(verbose_name=_("response data type"), blank=True)
    resp_text = models.TextField(verbose_name=_("response data in case failure occurs"), blank=True)
    parent = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="child_extraction")
    source_validation_status = models.IntegerField(
        verbose_name=_("source data validation status"), choices=ValidationStatus.choices
    )
    content_validation = models.TextField(verbose_name=_("validation status fail reason"), blank=True)
    revision_id = models.ForeignKey(
        "self",
        verbose_name=_("revision id"),
        help_text="This id points to the extraction object having same file content",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    hazard_type = models.CharField(max_length=100, verbose_name=_("hazard type"), choices=HazardType.choices, blank=True)

    def __str__(self):
        return str(self.id)


class GdacsTransformation(UserResource):
    class ItemType(models.IntegerChoices):
        EVENT = 1, "Event"
        HAZARD = 2, "Hazard"
        IMPACT = 3, "Impact"

    class TransformationStatus(models.IntegerChoices):
        FAILED = 1, "Failed"
        SUCCESS = 2, "Success"

    extraction = models.ForeignKey(ExtractionData, on_delete=models.PROTECT, null=True, blank=True)
    item_type = models.IntegerField(choices=ItemType.choices)
    data = models.JSONField(default=dict)
    status = models.IntegerField(choices=TransformationStatus.choices)
    failed_reason = models.TextField(blank=True)


class GlideTransformation(UserResource):
    extraction = models.ForeignKey(ExtractionData, on_delete=models.PROTECT, null=True, blank=True)
    data = models.JSONField(default=dict)
    status = models.IntegerField(choices=GdacsTransformation.TransformationStatus.choices)
    failed_reason = models.TextField(blank=True)
