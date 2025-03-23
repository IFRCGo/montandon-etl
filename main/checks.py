from django.core.checks import Tags, register


@register(Tags.compatibility)
def source_config_checks(app_configs, **kwargs):
    from .configs import etl_config

    return [
        *etl_config.checks,
    ]
