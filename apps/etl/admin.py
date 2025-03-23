from django.contrib import admin
from djangoql.admin import DjangoQLSearchMixin

from apps.common.admin import AdminReadOnlyMixin

from .models import EtlTrace, ExtractionData, PyStacLoadData, Transform


@admin.register(EtlTrace)
class EtlTraceAdmin(AdminReadOnlyMixin, admin.ModelAdmin):
    date_hierarchy = "created_at"

    list_display = (
        "id",
        "created_at",
    )


@admin.register(ExtractionData)
class ExtractionDataAdmin(AdminReadOnlyMixin, DjangoQLSearchMixin, admin.ModelAdmin):
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
class TransformAdmin(AdminReadOnlyMixin, DjangoQLSearchMixin, admin.ModelAdmin):
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
class PyStacLoadDataAdmin(AdminReadOnlyMixin, DjangoQLSearchMixin, admin.ModelAdmin):
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

    def get_queryset(self, request):
        # NOTE: item contains heavy json data
        return super().get_queryset(request).defer("item")
