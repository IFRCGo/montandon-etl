from django.conf import settings
from django.core.checks import Tags, Warning, register


@register(Tags.compatibility)
def source_config_checks(app_configs, **kwargs):
    errors = []
    for label, value in [
        ("EOAPI_DOMAIN", settings.EOAPI_DOMAIN),
        ("EMDAT_AUTHORIZATION_KEY", settings.EMDAT_AUTHORIZATION_KEY),
        ("GFD_CREDENTIAL", settings.GFD_CREDENTIAL),
        ("GFD_SERVICE_ACCOUNT", settings.GFD_SERVICE_ACCOUNT),
        ("IDMC_CLIENT_ID", settings.IDMC_CLIENT_ID),
        ("PDC_ARCGIS_PASSWORD", settings.PDC_ARCGIS_PASSWORD),
        ("PDC_ARCGIS_USERNAME", settings.PDC_ARCGIS_USERNAME),
        ("PDC_SENTRY_AUTHORIZATION_KEY", settings.PDC_SENTRY_AUTHORIZATION_KEY),
    ]:
        if value not in [None, ""]:
            continue
        errors.append(Warning(f"{label} is not defined!"))
    return errors
