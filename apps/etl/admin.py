from django.contrib import admin

# Register your models here.
from .models import ExtractionData


@admin.register(ExtractionData)
class ExtractionDataAdmin(admin.ModelAdmin):
    list_display = (
        "source",
        "resp_code",
        "status",
        "resp_type",
    )
    list_filter = ("status",)
