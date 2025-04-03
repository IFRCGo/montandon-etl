import abc
import json
import logging
import typing
from typing import Any

import requests

from apps.etl.extraction.sources.base.utils import (
    hash_file_content,
    manage_duplicate_file_content,
)
from apps.etl.models import ExtractionData, get_trace_id
from main.logging import log_extra

logger = logging.getLogger(__name__)


ExtractionMetaData = typing.TypeVar("ExtractionMetaData")


class ValidationResponse(typing.TypedDict):
    status: str


class BaseExtraction(abc.ABC, typing.Generic[ExtractionMetaData]):
    """
    Handles data extraction.
    """

    metadata_class: typing.Type[ExtractionMetaData]

    # def __init_subclass__(cls, **kwargs):
    #     super().__init_subclass__(**kwargs)
    #     if getattr(cls, "metadata_class", None) is None:
    #         raise NotImplementedError(f"Please define metadata_class for {cls}")
    #     if getattr(cls, "extract", None) is None:
    #         raise NotImplementedError(f"Please define extract method for {cls}")

    def get_headers(self) -> dict:
        return {"accept": "application/json"}

    def get_file_extension(self) -> str:
        return ".json"

    @abc.abstractmethod
    def extract(extraction_object: ExtractionData) -> int:
        """
        Not Implemented
        return extraction id
        """
        raise NotImplementedError()

    def run_get_request(self, extraction_object: ExtractionData, url: str, params: dict) -> int:
        response = requests.get(url, params=params, headers=self.get_headers(), timeout=120)
        response.raise_for_status()
        extraction_object.resp_code = response.status_code
        extraction_object.mark_as_ended(ExtractionData.Status.SUCCESS, update_fields=["resp_code"])

        # FIXME: Handle 204
        if response.status_code == 200 or response.status_code == 204:
            self.store_extraction_data(extraction_object.source, response, extraction_object.id)
            # Check if response contains data
            if response.status_code == 204:
                extraction_object.source_validation_status = ExtractionData.ValidationStatus.NO_DATA
                extraction_object.mark_as_ended(ExtractionData.Status.SUCCESS, update_fields=["source_validation_status"])
                logger.warning("No hazard data found in response")

        return extraction_object.id

    def handle(self, id: int):
        extraction_object = ExtractionData.objects.get(id=id)
        extraction_object.mark_as_started()
        try:
            return self.extract(extraction_object)
        except requests.exceptions.RequestException:
            extraction_object.mark_as_ended(ExtractionData.Status.FAILED, update_fields=[])
            logger.error(
                "Extraction failed",
                exc_info=True,
                extra=log_extra({"source": extraction_object.source}),
            )
            raise

    def store_extraction_data(
        self,
        source: int,
        response: requests.Response,
        instance_id: int | None = None,
    ) -> ExtractionData:
        """
        Save extracted data into data base. Checks for duplicate conent using hashing.
        """
        extraction_instance = ExtractionData.objects.get(id=instance_id)

        file_extension = self.get_file_extension()
        file_name = f"{source}.{file_extension}"
        resp_data_content = response.content

        # save the additional response data after the data is fetched from api.
        extraction_instance.resp_data_type = response.headers.get("Content-Type", "")
        extraction_instance.save()

        # Validate the non empty response data.
        if resp_data_content:
            # Source validation
            # manage duplicate file content.
            hash_content = hash_file_content(resp_data_content)
            manage_duplicate_file_content(
                source=extraction_instance.source,
                hash_content=hash_content,
                instance=extraction_instance,
                response_data=resp_data_content,
                file_name=file_name,
            )
        return extraction_instance

    def create_extraction_instance(
        self,
        source: int,
        parent_id: int | None = None,
        status: ExtractionData.Status = ExtractionData.Status.PENDING,
        metadata: dict | None = {},
    ) -> int:
        """
        Create and return a new extraction instance with initial status.
        Returns:
            ExtractionData: The created extraction instance
        """
        parent = ExtractionData.objects.filter(id=parent_id).first()
        extraction_object = ExtractionData.objects.create(
            source=source,
            status=status,
            source_validation_status=ExtractionData.ValidationStatus.NO_VALIDATION,
            trace_id=get_trace_id(parent),
            hazard_type=metadata.events,
            parent_id=parent_id,
            metadata=metadata.model_dump(),
            attempt_no=0,
            resp_code=0,
        )
        return extraction_object.id

    def _update_instance_status(
        self, instance: ExtractionData, status: int, validation_status: int | None = None, update_validation: bool = False
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
        return instance

    def _save_response_data(self, instance: ExtractionData, response: requests.Response) -> dict:
        """
        Save the response data to the extraction instance.
        Args:
            instance: ExtractionData instance to save to
            response: Response object containing the data
        Returns:
            dict: Parsed JSON response content
        """
        instance = self.store_extraction_data(
            response=response,
            source=instance.source,
            instance_id=instance.id,
        )

        return json.loads(response.content)

    def handle_extraction(
        self,
        url: str,
        params: dict | None,
        headers: dict | None,
        source: int,
        parent_id: int | None = None,
        timeout: int = 30,
    ) -> int:
        """
        Process data extraction.
        Returns:
            int: ID of the extraction instance
        """
        logger.info("Starting data extraction")
        instance = self._create_extraction_instance(
            url=url,
            source=source,
            parent_id=parent_id,
            metadata={"input": params} if params else {},
        )

        try:
            self._update_instance_status(instance, ExtractionData.Status.IN_PROGRESS)

            response = requests.get(url, params=params, headers=headers, timeout=timeout)
            response.raise_for_status()
            instance.resp_code = response.status_code
            instance.save(update_fields=["resp_code"])

            # FIXME: Handle 204
            if response.status_code == 200 or response.status_code == 204:
                response_data = self._save_response_data(instance, response)
                # Check if response contains data
                if response_data:
                    self._update_instance_status(instance, ExtractionData.Status.SUCCESS)
                    logger.info("Data extracted successfully")
                else:
                    self._update_instance_status(
                        instance,
                        ExtractionData.Status.SUCCESS,
                        ExtractionData.ValidationStatus.NO_DATA,
                        update_validation=True,
                    )
                    logger.warning("No hazard data found in response")

            # FIXME: Handle else case
            return instance.id

        except requests.exceptions.RequestException:
            self._update_instance_status(instance, ExtractionData.Status.FAILED)
            logger.error(
                "Extraction failed",
                exc_info=True,
                extra=log_extra({"source": instance.source}),
            )
            raise

    # FIXME: Implement init subclass to check if abstract methods are implemented on subclasses
    @staticmethod
    @abc.abstractmethod
    def task(*args: Any, **kwargs: typing.Any):
        """
        Not NotImplemented due to celery limitation with classmethod
        Eg: return XYZExtraction.handle_extraction(url, source)
        """
        raise NotImplementedError()
