from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html


class AdminReadOnlyMixin:
    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# FIXME: Fix n+1 issue
def linkify(field_name: str, label: str | None = None):
    """
    Converts a foreign key value into clickable links.

    If field_name is 'parent', link text will be str(obj.parent)
    Link will be admin url for the admin url for obj.parent.id:change
    """

    short_description = label or " ".join(field_name.split("."))
    admin_order_field = "__".join(field_name.split("."))

    @admin.display(description=short_description, ordering=admin_order_field)
    def _linkify(obj):
        try:
            linked_obj = obj
            for _field_name in field_name.split("."):
                linked_obj = getattr(linked_obj, _field_name, None)
            if linked_obj:
                app_label = linked_obj._meta.app_label
                model_name = linked_obj._meta.model_name
                view_name = f"admin:{app_label}_{model_name}_change"
                link_url = reverse(view_name, args=[linked_obj.pk])
                return format_html(f'<a href="{link_url}">{linked_obj}</a>')
        except Exception:
            pass
        return "-"

    return _linkify
