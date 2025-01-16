from datetime import datetime
from typing import List, Optional, Union

from pydantic import BaseModel, HttpUrl


class URLDetails(BaseModel):
    geometry: HttpUrl
    report: HttpUrl
    details: HttpUrl


class SeverityData(BaseModel):
    severity: float
    severitytext: str
    severityunit: str


class AffectedCountry(BaseModel):
    iso3: str
    countryname: str


class Properties(BaseModel):
    eventtype: str
    eventid: int
    episodeid: int
    eventname: str
    glide: Optional[str]
    name: str
    description: str
    htmldescription: str
    icon: HttpUrl
    iconoverall: HttpUrl
    url: URLDetails
    alertlevel: str
    alertscore: float
    episodealertlevel: str
    episodealertscore: float
    istemporary: str
    iscurrent: str
    country: str
    fromdate: datetime
    todate: datetime
    datemodified: datetime
    iso3: str
    source: str
    sourceid: str
    polygonlabel: str
    Class: str
    country: str
    affectedcountries: List[AffectedCountry]
    severitydata: SeverityData


class Geometry(BaseModel):
    type: str
    coordinates: Union[List[float], List[List[List[float]]], List[List[List[List[float]]]]]


class Feature(BaseModel):
    type: str
    bbox: List[float]
    geometry: Geometry
    properties: Properties


class GdacsEventsGeometryData(BaseModel):
    type: str
    features: List[Feature]
