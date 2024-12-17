from pydantic import BaseModel, HttpUrl
from typing import List, Optional, Union
from datetime import datetime


# Nested Models
class Coordinates(BaseModel):
    type: str
    coordinates: List[float]


class URLData(BaseModel):
    geometry: HttpUrl
    report: HttpUrl
    media: HttpUrl


class AffectedCountry(BaseModel):
    iso3: str
    countryname: str


class SeverityData(BaseModel):
    severity: float
    severitytext: str
    severityunit: str


class EpisodeDetails(BaseModel):
    details: HttpUrl


class SendaiData(BaseModel):
    latest: bool
    sendaitype: str
    sendainame: str
    sendaivalue: Union[int, str]
    country: str
    region: str
    dateinsert: datetime
    description: str
    onset_date: datetime
    expires_date: datetime
    effective_date: Optional[datetime]


class Images(BaseModel):
    populationmap: Optional[HttpUrl]
    floodmap_cached: Optional[HttpUrl]
    thumbnailmap_cached: Optional[HttpUrl]
    rainmap_cached: Optional[HttpUrl]
    overviewmap_cached: Optional[HttpUrl]
    overviewmap: Optional[HttpUrl]
    floodmap: Optional[HttpUrl]
    rainmap: Optional[HttpUrl]
    rainmap_legend: Optional[HttpUrl]
    floodmap_legend: Optional[HttpUrl]
    overviewmap_legend: Optional[HttpUrl]
    rainimage: Optional[HttpUrl]
    meteoimages: Optional[HttpUrl]
    mslpimages: Optional[HttpUrl]
    event_icon_map: Optional[HttpUrl]
    event_icon: Optional[HttpUrl]
    thumbnailmap: Optional[HttpUrl]
    npp_icon: Optional[HttpUrl]


# Main Schema
class FeatureProperties(BaseModel):
    eventtype: str
    eventid: int
    episodeid: int
    eventname: Optional[str]
    glide: Optional[str]
    name: str
    description: str
    htmldescription: str
    icon: Optional[HttpUrl]
    iconoverall: Optional[str]
    url: URLData
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
    affectedcountries: List[AffectedCountry]
    severitydata: SeverityData
    episodes: List[EpisodeDetails]
    sendai: List[SendaiData]
    impacts: List[dict]
    images: Images
    additionalinfos: dict
    documents: dict


class GDacsEventDataValidator(BaseModel):
    type: str
    bbox: List[float]
    geometry: Coordinates
    properties: FeatureProperties
