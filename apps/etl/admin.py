from django.contrib import admin

# Register your models here.
from .models import ExtractionData


@admin.register(ExtractionData)
class ExtractionDataAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "source",
        "resp_code",
        "status",
        "parent__id",
        "resp_data_type",
    )
    list_filter = ("status",)
