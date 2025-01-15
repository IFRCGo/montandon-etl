from django.contrib import admin

# Register your models here.
from .models import ExtractionData, GdacsTransformation


@admin.register(ExtractionData)
class ExtractionDataAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, request, obj=None):
        # Use the model's fields to populate readonly_fields
        if obj:  # If the object exists (edit page)
            return [field.name for field in self.model._meta.fields]
        return []

    list_display = (
        "id",
        "source",
        "resp_code",
        "status",
        "parent__id",
        "resp_data_type",
        "source_validation_status",
        "hazard_type",
        "created_at",
    )
    list_filter = ("status",)
    autocomplete_fields = ["parent"]
    search_fields = ["parent"]


@admin.register(GdacsTransformation)
class GdacsTransformationAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, request, obj=None):
        # Use the model's fields to populate readonly_fields
        if obj:  # If the object exists (edit page)
            return [field.name for field in self.model._meta.fields]
        return []

    list_display = (
        "id",
        "extraction",
        "item_type",
        "status",
    )
    list_filter = ("status",)
    autocomplete_fields = ["extraction"]
    search_fields = ["extraction"]
