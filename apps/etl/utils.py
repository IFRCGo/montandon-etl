import datetime
import logging

import requests
from django.conf import settings
from django.core.files import File

logger = logging.getLogger(__name__)


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
        login_url = f"{settings.PDC_ARCGIS_DOMAIN}/arcgis/tokens/generateToken"
        data = {
            "f": "json",
            "username": settings.PDC_ARCGIS_USERNAME,
            "password": settings.PDC_ARCGIS_PASSWORD,
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
        url = f"{settings.PDC_ARCGIS_DOMAIN}/arcgis/rest/services/partners/pdc_hazard_exposure/MapServer/27/query"
        response = self.session.post(
            url=url,
            data={
                **ARC_GIS_DEFAULT_PARAMS,
                "where": f"hazard_uuid IN ('{uuid}')",
                "outFields": "hazard_uuid,type_id",
            },
        )

        return response.json()
