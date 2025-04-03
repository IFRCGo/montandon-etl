import base64
import datetime
import json
import pprint
from urllib.parse import urlparse

from django.conf import settings
from django.core.checks import CheckMessage, Error, Info, Warning


def decode_json(encoded_str: str):
    """Decodes a Base64 string back to a JSON object."""
    decoded_data = base64.urlsafe_b64decode(encoded_str.encode()).decode()
    return json.loads(decoded_data)


# TODO: Add test cases for each parse_*
# TODO: Add proper explanation for the type ignores (How django handles the checks)
class EtlConfig:
    """
    To manage the parsing and validation of ETL configuration

    This class provides methods to:
    - Parse non-empty values from Django settings.
    - Parse and validate base URLs
    - Track checks (warnings and information) related to ETL configurations.
    """

    def parse_non_empty_value(self, settings_key: str) -> str:
        value = getattr(settings, settings_key)
        if value in [None, ""]:
            self.checks.append(
                Warning(
                    f"{settings_key}: Empty value",
                )
            )
        return value

    def parse_int_value_required(self, settings_key: str) -> int:  # type: ignore[reportReturnType]
        value = getattr(settings, settings_key)
        if value in [None, ""]:
            self.checks.append(
                Error(
                    f"{settings_key}: Empty value",
                )
            )
            return None  # type: ignore[reportReturnType]
        try:
            return int(value)
        except Exception:
            self.checks.append(
                Warning(
                    f"{settings_key}: Invalid value. {value}",
                )
            )

    def parse_date_value_required(self, settings_key: str) -> datetime.date:  # type: ignore[reportReturnType]
        value = getattr(settings, settings_key)
        if value in [None, ""]:
            self.checks.append(Error(f"{settings_key}: Empty value"))
            return None  # type: ignore[reportReturnType]
        try:
            return datetime.datetime.strptime(value, "%Y-%m-%d").date()
        except Exception:
            self.checks.append(Error(f"{settings_key}: Invalid value. {value}"))

    def parse_json_value(self, settings_key: str) -> dict | None:
        value = getattr(settings, settings_key)
        if value in [None, ""]:
            self.checks.append(Warning(f"{settings_key}: Empty value"))
            return
        try:
            return decode_json(value)
        except Exception as e:
            self.checks.append(Warning(f"{settings_key}: {e}"))

    def parse_base_url(self, settings_key: str) -> str | None:
        """
        Parse and validate a base URL.
        If the URL is invalid, it appends a warning.
        If the URL is changed, it appends a info.
        """
        url = getattr(settings, settings_key)
        parsed = urlparse(url or "")
        errors = []
        if url in ["", None]:
            errors.append("Not defined")
        else:
            if parsed.scheme == "":
                errors.append("Missing scheme")
            if parsed.netloc == "":
                errors.append("Missing netlock")
        if errors:
            self.checks.append(
                Warning(
                    f"{settings_key}: " + ", ".join(errors),
                    hint=f"{url} -> {parsed}",
                )
            )
            return None
        new_url = f"{parsed.scheme}://{parsed.netloc}"
        if new_url != url:
            self.checks.append(
                Info(
                    f"{settings_key}: Value changed",
                    hint=f"{url} -> {new_url}",
                    id=settings_key,
                )
            )
        return new_url

    def parse_base_url_required(self, settings_key: str) -> str:
        """
        Parse and validate a base URL.
        If the URL is invalid, it appends a warning.
        If the URL is changed, it appends a info.
        """
        url = getattr(settings, settings_key)
        parsed = urlparse(url or "")
        errors = []
        if url in ["", None]:
            errors.append("Not defined")
        else:
            if parsed.scheme == "":
                errors.append("Missing scheme")
            if parsed.netloc == "":
                errors.append("Missing netlock")
        if errors:
            self.checks.append(
                Error(
                    f"{settings_key}: " + ", ".join(errors),
                    hint=f"{url} -> {parsed}",
                )
            )
            return None  # type: ignore[reportReturnType]
        new_url = f"{parsed.scheme}://{parsed.netloc}"
        if new_url != url:
            self.checks.append(
                Info(
                    f"{settings_key}: Value changed",
                    hint=f"{url} -> {new_url}",
                    id=settings_key,
                )
            )
        return new_url

    def __init__(self):
        # NOTE: Used by main/checks.py
        self.checks: list[CheckMessage] = []

        self.EOAPI_DOMAIN = self.parse_base_url("EOAPI_DOMAIN")
        self.EOAPI_SYNC_LIMIT = self.parse_int_value_required("EOAPI_SYNC_LIMIT")
        self.GEOCODER_URL = self.parse_base_url_required("GEOCODER_URL")

        self.DESINVENTAR_DATA_URL = self.parse_base_url_required("DESINVENTAR_DATA_URL")

        self.USGS_DATA_URL = self.parse_base_url_required("USGS_DATA_URL")
        self.USGS_START_DATE = self.parse_date_value_required("USGS_START_DATE")

        self.IBTRACS_DATA_URL = self.parse_base_url_required("IBTRACS_DATA_URL")

        # EMDAT
        self.EMDAT_URL = self.parse_base_url_required("EMDAT_URL")
        self.EMDAT_START_YEAR = self.parse_int_value_required("EMDAT_START_YEAR")
        self.EMDAT_AUTHORIZATION_KEY = self.parse_non_empty_value("EMDAT_AUTHORIZATION_KEY")

        # GDACS
        self.GDACS_URL = self.parse_base_url_required("GDACS_URL")
        self.GDACS_START_DATE = self.parse_date_value_required("GDACS_START_DATE")

        # GFD
        self.GFD_CREDENTIAL = self.parse_json_value("GFD_CREDENTIAL")
        self.GFD_SERVICE_ACCOUNT = self.parse_non_empty_value("GFD_SERVICE_ACCOUNT")

        # GLIDE
        self.GLIDE_URL = self.parse_base_url_required("GLIDE_URL")
        self.GLIDE_START_DATE = self.parse_date_value_required("GLIDE_START_DATE")

        # IDMC
        self.IDMC_DATA_URL = self.parse_base_url_required("IDMC_DATA_URL")
        self.IDMC_CLIENT_ID = self.parse_non_empty_value("IDMC_CLIENT_ID")

        # IFRC
        self.IFRC_DATA_URL = self.parse_base_url_required("IFRC_DATA_URL")
        self.IFRC_EVENT_START_DATE = self.parse_date_value_required("IFRC_EVENT_START_DATE")

        # PDC
        # -- ARC GIS
        self.PDC_ARCGIS_DOMAIN = self.parse_base_url_required("PDC_ARCGIS_DOMAIN")
        # -- Credentials
        self.PDC_ARCGIS_PASSWORD = self.parse_non_empty_value("PDC_ARCGIS_PASSWORD")
        self.PDC_ARCGIS_USERNAME = self.parse_non_empty_value("PDC_ARCGIS_USERNAME")
        # -- Sentry
        self.PDC_SENTRY_BASE_URL = self.parse_base_url_required("PDC_SENTRY_BASE_URL")
        self.PDC_SENTRY_AUTHORIZATION_KEY = self.parse_non_empty_value("PDC_SENTRY_AUTHORIZATION_KEY")

    def debug_print(self):
        pprint.pp(self.__dict__, indent=2)


etl_config = EtlConfig()
# etl_config.debug_print()
