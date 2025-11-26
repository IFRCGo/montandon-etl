from enum import Enum


class GdacsExtractionMetadataType(str, Enum):
    QUERY = "QUERY"
    DETAIL = "DETAIL"
    GEOMETRY = "GEOMETRY"
    EPISODE = "EPISODE"
    IMPACT = "IMPACT"
