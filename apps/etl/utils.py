import logging

logger = logging.getLogger(__name__)

LOCAL_CACHE_DATA_DIR_MAP = {
    "gaul_geocoder": "gaul2014_2015.gpkg",
}


def read_file_data(file):
    """
    Read file content and return the content of the file
    """
    with file.open() as data_file:
        data = data_file.read()
    return data
