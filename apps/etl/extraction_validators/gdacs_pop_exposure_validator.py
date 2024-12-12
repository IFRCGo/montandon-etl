from pydantic import BaseModel


class PopulationExposureEQTC(BaseModel):
    exposed_population: str


class PopulationExposure_FL(BaseModel):
    death: int
    displaced: int


class PopulationExposureDR(BaseModel):
    impact: str


class PopulationExposureWF(BaseModel):
    people_affected: str
