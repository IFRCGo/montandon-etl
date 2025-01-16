from typing import Optional, Union

from pydantic import BaseModel


class GdacsPopulationExposureEQTC(BaseModel):
    exposed_population: Optional[str]


class GdacsPopulationExposure_FL(BaseModel):
    death: int
    displaced: Optional[Union[int, str]]


class GdacsPopulationExposureDR(BaseModel):
    impact: str


class GdacsPopulationExposureWF(BaseModel):
    people_affected: str
