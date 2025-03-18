from django.contrib import admin

# Register your models here.
from .models import ExtractionData, PyStacLoadData, Transform


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
        "trace_id",
        "created_at",
    )
    list_filter = ("status", "source")
    autocomplete_fields = ["parent"]
    search_fields = ["parent"]


@admin.register(Transform)
class TransformAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, request, obj=None):
        # Use the model's fields to populate readonly_fields
        if obj:  # If the object exists (edit page)
            return [field.name for field in self.model._meta.fields]
        return []

    list_display = ("id", "extraction", "status", "trace_id", "is_loaded")
    list_filter = ("status",)
    autocomplete_fields = ["extraction"]
    search_fields = ["extraction"]


@admin.register(PyStacLoadData)
class PyStacLoadDataAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, request, obj=None):
        # Use the model's fields to populate readonly_fields
        if obj:  # If the object exists (edit page)
            return [field.name for field in self.model._meta.fields]
        return []

    list_display = (
        "id",
        "transform_id",
        "item_type",
        "load_status",
        "collection_id",
        "trace_id",
    )
    list_filter = ("load_status",)
    autocomplete_fields = ["transform_id"]
    search_fields = ["transform_id"]
