from pydantic import BaseModel


class GdacsPopulationExposureEQTC(BaseModel):
    exposed_population: str


class GdacsPopulationExposure_FL(BaseModel):
    death: int
    displaced: int


class GdacsPopulationExposureDR(BaseModel):
    impact: str


class GdacsPopulationExposureWF(BaseModel):
    people_affected: str
