import logging

logger = logging.getLogger(__name__)


def read_file_data(file):
    """
    Read file content and return the content of the file
    """
    with file.open() as data_file:
        data = data_file.read()
    return data
