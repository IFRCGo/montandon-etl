import logging
from datetime import datetime, timedelta
import json
import requests
from django.core.files.base import ContentFile
from apps.etl.extraction.sources.base.extract import Extraction
from apps.etl.extraction.sources.base.utils import store_extraction_data
from apps.etl.models import ExtractionData

logger = logging.getLogger(__name__)


class IDUExtraction(Extraction):
    """
    Handles data extraction from the IDU API for hazard data.
    """
    BASE_URL = "https://helix-tools-api.idmcdb.org/external-api/idus/last-180-days/"
    CLIENT_ID = "IDMCWSHSOLO009"

    def __init__(self, url: str = None):
        """
        Initialize the IDU extraction process.
        Args:
            url (str, optional): Override the default API URL. Defaults to BASE_URL.
        """
        super().__init__(url or self.BASE_URL)
        self.headers = {"accept": "application/json"}
        self.params = {"client_id": self.CLIENT_ID}

    def _create_extraction_instance(self) -> ExtractionData:
        """
        Create and return a new extraction instance with initial status.
        Returns:
            ExtractionData: The created extraction instance
        """
        return ExtractionData.objects.create(
            source=ExtractionData.Source.IDU,
            status=ExtractionData.Status.PENDING,
            source_validation_status=ExtractionData.ValidationStatus.NO_VALIDATION,
            hazard_type=None,
            attempt_no=0,
            resp_code=0
        )

    def _update_instance_status(
        self,
        instance: ExtractionData,
        status: int,
        validation_status: str = None,
        update_validation: bool = False
    ) -> None:
        """
        Update the status of the extraction instance.
        Args:
            instance: ExtractionData instance to update
            status: New status to set
            validation_status: Optional validation status to set
            update_validation: Whether to update validation status
        """
        instance.status = status
        if update_validation and validation_status:
            instance.source_validation_status = validation_status
            instance.save(update_fields=["status", "source_validation_status"])
        else:
            instance.save(update_fields=["status"])

    def _save_response_data(
        self,
        instance: ExtractionData,
        response: requests.Response
    ) -> dict:
        """
        Save the response data to the extraction instance.
        Args:
            instance: ExtractionData instance to save to
            response: Response object containing the data
        Returns:
            dict: Parsed JSON response content
        """
        file_name = f"idu_disaster_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        instance.resp_data.save(file_name, ContentFile(response.content))
        return json.loads(response.content)

    def process_data(self) -> int:
        """
        Process IDU hazard data extraction.
        Returns:
            int: ID of the extraction instance
        """
        logger.info("Starting IDU data extraction")
        instance = self._create_extraction_instance()

        try:
            self._update_instance_status(instance, ExtractionData.Status.IN_PROGRESS)

            response = requests.get(
                self.url,
                params=self.params,
                headers=self.headers,
                timeout=30
            )
            response.raise_for_status()
            instance.resp_code = response.status_code

            if response.status_code == 200:
                response_data = self._save_response_data(instance, response)
                # Check if response contains data
                if response_data:
                    self._update_instance_status(
                        instance,
                        ExtractionData.Status.SUCCESS,
                        ExtractionData.ValidationStatus.NO_DATA,
                        update_validation=True
                    )
                    logger.warning("No hazard data found in IDU response")
                else:
                    self._update_instance_status(instance, ExtractionData.Status.SUCCESS)
                    logger.info("IDU data extracted successfully")

            return instance.id

        except requests.exceptions.RequestException as e:
            self._update_instance_status(instance, ExtractionData.Status.FAILED)
            logger.error(
                "IDU extraction failed",
                exc_info=True,
                extra={
                    "source": ExtractionData.Source.IDU,
                    "error": str(e)
                }
            )
            raise
