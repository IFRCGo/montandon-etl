import io
import logging
import zipfile
from pathlib import Path

import requests

logger = logging.getLogger(__name__)


def extract_country_data(country_code: str):
    logger.info(f"Desinventar: Extraction started for {country_code}")
    print(f"Desinventar: Extraction started for {country_code}")

    # TODO: this should come from utils
    output_dir = "/tmp/desinventar/{country_code}/"

    xml_file_path = f"{output_dir}/DI_export_{country_code}.xml"

    if Path(xml_file_path).exists():
        logger.info(f"Desinventar: Required file already exists, skipping download for {country_code}")
        print(f"Desinventar: Required file already exists, skipping download for {country_code}")
        return

    # desinventar_trigger_url = f"https://www.desinventar.net/DesInventar/download_base.jsp?country_code={country_code}"
    # TODO: this should come from utils
    desinventar_download_url = f"https://www.desinventar.net/DesInventar/download/DI_export_{country_code}.zip"

    try:
        logger.info(f"Desinventar: Downloading data for {country_code} from {desinventar_download_url}")
        response = requests.get(desinventar_download_url, stream=True)
        with io.BytesIO(response.content) as inmemoryZip:
            logger.info(f"Desinventar: Download successful for {country_code}")
            logger.info(f"Desinventar: Unzipping results to {output_dir}")
            with zipfile.ZipFile(inmemoryZip, "r") as zip_ref:
                zip_ref.extractall(output_dir)
                # TODO: verify extract

        logger.error(f"Desinventar: Extraction successful for {country_code}")
        print(f"Desinventar: Extraction successful for {country_code}")

    except requests.exceptions.RequestException as e:
        logger.error(f"Desinventar: Extraction failed for {country_code}: {str(e)}")
        print(f"Desinventar: Extraction failed for {country_code}: {str(e)}")
        raise Exception(f"Request failed: {e}")

    logger.info(f"Desinventar: Extraction ended for {country_code}")
    print(f"Desinventar: Extraction ended for {country_code}")
