import json
import urllib.parse

from django.contrib import admin
from django.db import models
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Cast
from django.utils.safestring import mark_safe
from djangoql.admin import DjangoQLSearchMixin

from apps.common.admin import linkify

from .models import EtlTrace, ExtractionData, PyStacLoadData, Transform


class EtlResourceAdminMixin(admin.ModelAdmin):
    @admin.display(description="Total Rows", ordering="total_rows")
    def total_rows(self, instance):
        return instance.total_rows

    @admin.display(description="Success (%)", ordering="success_percentage")
    def success_percentage(self, instance):
        return instance.success_percentage

    @admin.display(description="Execution time", ordering="execution_time")
    def execution_time(self, instance):
        return instance.execution_time

    @admin.display(description="Wait time", ordering="wait_time")
    def wait_time(self, instance):
        return instance.wait_time

    def get_queryset(self, request):
        total_rows = Cast(
            KeyTextTransform(
                "total_rows",
                KeyTextTransform("summary", "metadata"),
            ),
            models.IntegerField(),
        )

        failed_rows = Cast(
            KeyTextTransform(
                "failed_rows",
                KeyTextTransform("summary", "metadata"),
            ),
            models.FloatField(),
        )

        return (
            super()
            .get_queryset(request)
            .annotate(
                total_rows=total_rows,
                wait_time=models.F("started_at") - models.F("created_at"),
                execution_time=models.F("ended_at") - models.F("started_at"),
                success_percentage=models.Case(
                    models.When(total_rows=0, then=models.Value(0)),
                    default=100 * (1 - (failed_rows / total_rows)),
                    output_field=models.FloatField(),
                ),
            )
        )


@admin.register(EtlTrace)
class EtlTraceAdmin(admin.ModelAdmin):
    date_hierarchy = "created_at"

    list_display = (
        "id",
        "created_at",
    )


@admin.register(ExtractionData)
class ExtractionDataAdmin(DjangoQLSearchMixin, admin.ModelAdmin):
    list_display = (
        "id",
        linkify("trace"),
        linkify("parent"),
        "source",
        "metadata",
        "status",
        "source_validation_status",
        "resp_code",
        "resp_data",
        "resp_data_type",
        "hazard_type",
        "created_at",
        "started_at",
        "ended_at",
    )
    list_filter = ("status", "source", "source_validation_status")
    autocomplete_fields = ["parent"]
    search_fields = ["parent"]


@admin.register(Transform)
class TransformAdmin(EtlResourceAdminMixin, DjangoQLSearchMixin, admin.ModelAdmin):
    list_display = (
        "id",
        linkify("trace"),
        linkify("extraction"),
        "source",
        "status",
        "created_at",
        "wait_time",
        "started_at",
        "ended_at",
        "execution_time",
        "success_percentage",
        "total_rows",
    )
    list_filter = ("status", "extraction_id__source")
    autocomplete_fields = ["extraction"]
    search_fields = ["extraction"]

    @admin.display(description="Source", ordering="source")
    def source(self, instance):
        return ExtractionData.Source(instance.source).label

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(
                source=models.F("extraction__source"),
            )
        )


@admin.register(PyStacLoadData)
class PyStacLoadDataAdmin(DjangoQLSearchMixin, admin.ModelAdmin):
    list_display = (
        "id",
        linkify("trace"),
        linkify("transform_id"),
        "collection_id",
        "item_type",
        "status",
        "created_at",
        "item_id",
        "item_datetime",
        "item_primary_country",
    )
    list_filter = (
        "item_type",
        "status",
        "transform_id__extraction_id__source",
    )
    list_filter = ("item_type", "status", "transform_id__extraction_id__source")
    autocomplete_fields = ["transform_id"]
    search_fields = ["transform_id"]
    readonly_fields = ["view_map"]

    @admin.display(description="Source", ordering="source")
    def source(self, instance):
        return ExtractionData.Source(instance.source).label

    def get_geojson_io_url(self, geojson_data):
        encoded_data = urllib.parse.quote(json.dumps(geojson_data))
        return f"https://geojson.io/#data=data:application/json,{encoded_data}"

    def view_map(self, obj):
        if obj.item.get("geometry"):
            url = self.get_geojson_io_url(obj.item["geometry"])
            return mark_safe(f'<a href="{url}" target="_blank">View on GeoJson.io</a>')
        return "No GeoJSON data available"

    def get_queryset(self, request):
        # NOTE: item contains heavy json data
        return super().get_queryset(request).defer("item")
