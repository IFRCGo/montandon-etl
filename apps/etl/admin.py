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
        "trace_id",
        "id",
        "parent_id",
        "source",
        "metadata",
        "status",
        "source_validation_status",
        "resp_code",
        "resp_data",
        "resp_data_type",
        "hazard_type",
        "created_at",
    )
    list_filter = ("status", "source", "source_validation_status")
    autocomplete_fields = ["parent"]
    search_fields = ["parent"]


@admin.register(Transform)
class TransformAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, request, obj=None):
        # Use the model's fields to populate readonly_fields
        if obj:  # If the object exists (edit page)
            return [field.name for field in self.model._meta.fields]
        return []

    list_display = (
        "trace_id",
        "id",
        "extraction",
        "status",
        "is_loaded",
        "created_at",
    )
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
        "trace_id",
        "id",
        "transform_id",
        "collection_id",
        "item_type",
        "load_status",
        "created_at",
    )
    list_filter = (
        "item_type",
        "load_status",
    )
    autocomplete_fields = ["transform_id"]
    search_fields = ["transform_id"]
