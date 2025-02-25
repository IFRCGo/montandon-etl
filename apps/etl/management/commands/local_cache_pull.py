import logging
import os
import zipfile

import requests
from django.conf import settings
from django.core.management.base import BaseCommand

from apps.etl.utils import LOCAL_CACHE_DATA_DIR_MAP

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Load data to stac api"

    def handle(self, *args, **options):
        """
        Checks and Downloads the gaul file
        if it doesn't exist and returns the file path
        """
        filename = "gaul_gpkg.zip"
        chunk_size = 128
        timeout: int = 30
        url = "https://files.emdat.be/data/gaul_gpkg_and_license.zip"

        gpkg_dir_base_path = settings.LOCAL_CACHE_DATA_DIR

        zip_file_path = f"/tmp/{filename}"
        gaul_file_path = f"{gpkg_dir_base_path}/{LOCAL_CACHE_DATA_DIR_MAP["gaul_geocoder"]}"

        if not os.path.isdir(gpkg_dir_base_path):
            os.makedirs(gpkg_dir_base_path)

        if os.path.exists(gaul_file_path):
            logger.info("The file already exists in the path.")
            return gaul_file_path

        logging.info("File Download has started.")
        try:
            response = requests.get(url=url, stream=True, timeout=timeout)
        except (requests.Timeout, requests.ReadTimeout) as e:
            raise Exception("Timout occurred while downloading the zip gpkg file. %s", e)

        if response.status_code == 200:
            with open(zip_file_path, "wb") as file:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    file.write(chunk)
            logger.info("File downloaded successfully.")
            logger.info("Extracting zip contents.")
            try:
                with zipfile.ZipFile(zip_file_path, "r") as zip_ref:
                    zip_ref.extractall(gpkg_dir_base_path)
            except zipfile.BadZipFile:
                logger.error("Couldn't extract the zip contents.")
                return None
            if os.path.exists(zip_file_path):
                os.remove(zip_file_path)
            logger.info("Extraction done successfully.")
            logger.info(f"File loaded to directory: {settings.LOCAL_CACHE_DATA_DIR}")
            return gaul_file_path

        logger.error("Failed to download file. Status code: %s", response.status_code)
        return None
