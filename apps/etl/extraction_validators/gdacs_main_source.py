from typing import List, Optional

from pydantic import BaseModel, HttpUrl


class Urls(BaseModel):
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
    url: Urls
    alertlevel: str
    alertscore: float
    episodealertlevel: str
    episodealertscore: float
    istemporary: str
    iscurrent: str
    country: str
    fromdate: str
    todate: str
    datemodified: str
    iso3: str
    source: str
    sourceid: Optional[str]
    polygonlabel: str
    Class: str
    country: str
    affectedcountries: List[AffectedCountry]
    severitydata: SeverityData


class Geometry(BaseModel):
    type: str
    coordinates: List[float]


class Feature(BaseModel):
    type: str
    bbox: List[float]
    geometry: Geometry
    properties: Properties


class GdacsEventSourceValidator(BaseModel):
    type: str
    features: List[Feature]
