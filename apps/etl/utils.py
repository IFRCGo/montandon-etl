import datetime
import logging
import os
import tempfile
from pathlib import Path

import pandas as pd
import requests
from django.core.files import File

from main.configs import etl_config

logger = logging.getLogger(__name__)


def write_into_temp_file(content):
    temp_file = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    temp_file.write(content)
    temp_file.close()
    return temp_file


def get_cluster_codes():
    hazard_profiles_path = Path("./libs/pystac-monty/pystac_monty/HazardProfiles.csv")
    if os.path.exists(hazard_profiles_path):
        df = pd.read_csv(hazard_profiles_path)
        return list(df.emdat_key.dropna().unique())
    return []


def read_file_data(file: File) -> str:
    """
    Read file content and return the content of the file
    """
    with file.open() as data_file:
        return data_file.read()


ARC_GIS_DEFAULT_PARAMS = {
    "geometryType": "esriGeometryEnvelope",
    "spatialRel": "esriSpatialRelIntersects",
    "returnGeometry": True,
    "returnTrueCurves": False,
    "returnIdsOnly": False,
    "returnCountOnly": False,
    "returnZ": False,
    "returnM": False,
    "returnDistinctValues": False,
    "returnExtentOnly": False,
    "featureEncoding": "esriDefault",
    "f": "geojson",
    "text": "",
    "objectIds": "",
    "time": "",
    "geometry": "",
    "inSR": "",
    "relationParam": "",
    "outFields": "",
    "maxAllowableOffset": "",
    "geometryPrecision": "",
    "outSR": "",
    "having": "",
    "orderByFields": "",
    "groupByFieldsForStatistics": "",
    "outStatistics": "",
    "gdbVersion": "",
    "historicMoment": "",
    "resultOffset": "",
    "resultRecordCount": "",
    "queryByDistance": "",
    "datumTransformation": "",
    "parameterValues": "",
    "rangeValues": "",
    "quantizationParameters": "",
}


# FIXME: Rename this to PdcArcGisAccessor
class AccessTokenManager:
    def __init__(self, session: requests.Session):
        self.token_expires: datetime.datetime | None = None
        self.access_token: str | None = None
        self.session = session
        self.update()  # Ensure the token is fetched on initialization

    def get_access_token(self):
        login_url = f"{etl_config.PDC_ARCGIS_DOMAIN}/arcgis/tokens/generateToken"
        data = {
            "f": "json",
            "username": etl_config.PDC_ARCGIS_USERNAME,
            "password": etl_config.PDC_ARCGIS_PASSWORD,
            "referer": "https://www.arcgis.com",
        }
        login_response = self.session.post(login_url, data=data, allow_redirects=True).json()
        self.access_token = login_response["token"]
        self.token_expires = datetime.datetime.fromtimestamp(login_response["expires"] / 1000)
        return self.access_token, self.token_expires

    def update(self):
        if self.token_expires is None or datetime.datetime.now() >= self.token_expires:
            self.get_access_token()
            self.session.headers.update({"Authorization": f"Bearer {self.access_token}"})

    def get_polygon(self, uuid):
        url = f"{etl_config.PDC_ARCGIS_DOMAIN}/arcgis/rest/services/partners/pdc_hazard_exposure/MapServer/27/query"
        response = self.session.post(
            url=url,
            data={
                **ARC_GIS_DEFAULT_PARAMS,
                "where": f"hazard_uuid IN ('{uuid}')",
                "outFields": "hazard_uuid,type_id",
            },
        )

        return (response.json(), url)


def generate_item_index_fields_values(transformed_item: dict):
    item_id = transformed_item["id"]
    item_datetime = transformed_item["properties"]["datetime"]
    item_primary_country = transformed_item["properties"]["monty:country_codes"]

    logger.info("Item extracted: id=%s, datetime=%s, country=%s", item_id, item_datetime, item_primary_country)
    return item_id, item_datetime, item_primary_country
<<<<<<< HEAD


def remove_ignored_keys(obj, keys_to_ignore):
    """
    Recursively remove keys from dicts if the key is in keys_to_ignore.
    Works on nested dicts and lists.
    """
    if isinstance(obj, dict):
        for key in list(obj.keys()):
            if key in keys_to_ignore:
                obj.pop(key)
            else:
                remove_ignored_keys(obj[key], keys_to_ignore)
    elif isinstance(obj, list):
        for item in obj:
            remove_ignored_keys(item, keys_to_ignore)
    return obj
||||||| parent of d057542 (IDU E2E test with necessary changes)
=======

def remove_ignored_keys(obj, keys_to_ignore):
    """
    Recursively remove keys from dicts if the key is in keys_to_ignore.
    Works on nested dicts and lists.
    """
    if isinstance(obj, dict):
        for key in list(obj.keys()):
            if key in keys_to_ignore:
                obj.pop(key)
            else:
                remove_ignored_keys(obj[key], keys_to_ignore)
    elif isinstance(obj, list):
        for item in obj:
            remove_ignored_keys(item, keys_to_ignore)
    return obj
>>>>>>> d057542 (IDU E2E test with necessary changes)
