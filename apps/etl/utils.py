import logging

logger = logging.getLogger(__name__)


def read_file_data(file):
    '''
    Read file content and return the content of the file
    '''
    try:
        with file.open() as data_file:
            data = data_file.read()
        return data

    except FileNotFoundError:
        logger.error("File not found")
        raise
    except IOError as e:
        logger.error(f"I/O error while reading file: {str(e)}")
        raise
