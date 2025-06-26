import abc
import json
import logging
import typing
from typing import Any, Callable, Optional

import pydantic
import requests
from django.db import models
from django.utils.functional import cached_property

from apps.etl.extraction.sources.base.utils import hash_file_content, manage_duplicate_file_content
from apps.etl.models import ExtractionData, get_trace_id
from main.celery import CeleryQueue, app
from main.configs import etl_config
from main.logging import log_extra
from main.sentry import SentryTag
from utils.celery import RetryableTask
from utils.requests import RateLimitError

logger = logging.getLogger(__name__)


class NoDataException(Exception): ...


class ValidationResponse(typing.TypedDict):
    status: str


class BaseExtraction:
    """
    Handles data extraction.
    """

    @classmethod
    def store_extraction_data(
        cls,
        validate_source_func: Callable[[Any], ValidationResponse] | None,
        source: int,  # FIXME: Get this from instance
        response: requests.Response,
        instance_id: int | None = None,  # FIXME: Send object here instead of id
    ) -> ExtractionData:
        """
        Save extracted data into data base. Checks for duplicate conent using hashing.
        """
        file_extension = "json"
        file_name = f"{source}.{file_extension}"
        resp_data_content = response.content

        # save the additional response data after the data is fetched from api.
        extraction_instance = ExtractionData.objects.get(id=instance_id)
        extraction_instance.resp_data_type = response.headers.get("Content-Type", "")
        extraction_instance.save()

        # Validate the non empty response data.
        if resp_data_content:
            # Source validation
            # FIXME: Is validate_source_func being used?
            if validate_source_func:
                extraction_instance.source_validation_status = validate_source_func(resp_data_content)["status"]

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

    @classmethod
    def _create_extraction_instance(
        cls,
        url: str,
        source: int,
        parent_id: int | None = None,
        status: ExtractionData.Status = ExtractionData.Status.PENDING,
        hazard_type: str | None = None,
        metadata: dict | None = {},
    ) -> ExtractionData:
        """
        Create and return a new extraction instance with initial status.
        Returns:
            ExtractionData: The created extraction instance
        """
        parent = ExtractionData.objects.filter(id=parent_id).first()
        return ExtractionData.objects.create(
            source=source,
            url=url,
            status=status,
            source_validation_status=ExtractionData.ValidationStatus.NO_VALIDATION,
            trace_id=get_trace_id(parent),
            hazard_type=hazard_type,
            parent_id=parent_id,
            metadata=metadata,
            attempt_no=0,
            resp_code=0,
        )

    @classmethod
    def _update_instance_status(
        cls, instance: ExtractionData, status: int, validation_status: int | None = None, update_validation: bool = False
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

    @classmethod
    def _save_response_data(cls, instance: ExtractionData, response: requests.Response) -> dict:
        """
        Save the response data to the extraction instance.
        Args:
            instance: ExtractionData instance to save to
            response: Response object containing the data
        Returns:
            dict: Parsed JSON response content
        """
        instance = cls.store_extraction_data(
            response=response,
            source=instance.source,
            validate_source_func=None,
            instance_id=instance.id,
        )

        return json.loads(response.content)

    @classmethod
    def handle_extraction(
        cls,
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
        instance = cls._create_extraction_instance(
            url=url,
            source=source,
            parent_id=parent_id,
            metadata={"input": params} if params else {},
        )
        SentryTag.set_tags(
            {SentryTag.Tag.SOURCE: ExtractionData.Source(source).label, SentryTag.Tag.TRACE_ID: instance.trace_id}
        )

        try:
            cls._update_instance_status(instance, ExtractionData.Status.IN_PROGRESS)

            response = requests.get(url, params=params, headers=headers, timeout=timeout)
            response.raise_for_status()
            instance.resp_code = response.status_code
            instance.save(update_fields=["resp_code"])

            # FIXME: Handle 204
            if response.status_code == 200 or response.status_code == 204:
                response_data = cls._save_response_data(instance, response)
                # Check if response contains data
                if response_data:
                    cls._update_instance_status(instance, ExtractionData.Status.SUCCESS)
                    logger.info("Data extracted successfully")
                else:
                    cls._update_instance_status(
                        instance,
                        ExtractionData.Status.SUCCESS,
                        ExtractionData.ValidationStatus.NO_DATA,
                        update_validation=True,
                    )
                    logger.warning("No hazard data found in response")

            # FIXME: Handle else case
            return instance.id

        except requests.exceptions.RequestException:
            cls._update_instance_status(instance, ExtractionData.Status.FAILED)
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


ExtractionMetadataTypeVar = typing.TypeVar("ExtractionMetadataTypeVar", bound=pydantic.BaseModel)


class BaseExtractionV2(typing.Generic[ExtractionMetadataTypeVar]):
    MAX_RETRY_LIMIT = 5
    MAX_RATE_LIMIT_RETRY_LIMIT = 10
    MIN_RETRY_DELAY = 30
    MAX_RETRY_DELAY = 60
    RETRY_STATUS_CODE = [403, 429]
    DEFAULT_CELERY_QUEUE = CeleryQueue.EXTRACTION

    source_enum: ExtractionData.Source
    extraction_metadata_class: type[ExtractionMetadataTypeVar]

    # TODO(thenav56): Add __init_subclass__ to validate extraction_metadata_class is defined in subclass

    def __init__(self, celery_task: RetryableTask, extraction_id: int):
        self.celery_task = celery_task
        self.extraction_object = ExtractionData.objects.get(id=extraction_id)
        self.proxies = etl_config.get_http_proxy()
        SentryTag.set_tags(
            {
                SentryTag.Tag.SOURCE: ExtractionData.Source(self.extraction_object.source).label,
                SentryTag.Tag.TRACE_ID: self.extraction_object.trace_id,
            }
        )
        self.reparse_extraction_metadata()

    @cached_property
    def celery_queue(self) -> str:
        current_queue = getattr(self.celery_task.request, "delivery_info", {}).get("routing_key")
        return current_queue or self.DEFAULT_CELERY_QUEUE

    def reparse_extraction_metadata(self):
        self.extraction_metadata = self.extraction_metadata_class(**self.extraction_object.metadata)

    @classmethod
    def _extraction_store_data(
        cls,
        *,
        extraction_object: ExtractionData,
        response: requests.Response,
        file_extension: str = "json",
        content_type: str | None = None,
    ) -> ExtractionData:
        """
        Save extracted data into data base. Checks for duplicate content using hashing.
        """
        file_name = f"{extraction_object.source}.{file_extension}"
        resp_data_content = response.content

        # save the additional response data after the data is fetched from api.
        extraction_object.resp_data_type = content_type or response.headers.get("Content-Type", "")
        # FIXME: Is this required
        extraction_object.save()

        # Validate the non empty response data.
        if resp_data_content:
            # manage duplicate file content. FIXME: Does this work
            hash_content = hash_file_content(resp_data_content)
            manage_duplicate_file_content(
                source=extraction_object.source,
                hash_content=hash_content,
                instance=extraction_object,
                response_data=resp_data_content,
                file_name=file_name,
            )
        return extraction_object

    def _extraction_fetch_graphql(self, url: str, payload: dict, headers: Optional[dict] = None) -> bool:
        if not payload or "query" not in payload:
            return False
        response = requests.post(url, json=payload, headers=headers, proxies=self.proxies)
        response.raise_for_status()
        self.extraction_object.resp_code = response.status_code

        if response.status_code in [200, 204]:
            response_data = self._extraction_store_data(
                extraction_object=self.extraction_object,
                response=response,
            )
            # Check if response contains data
            if response_data:
                logger.info("Data extracted successfully")
                return True
            logger.warning("No data found in response")
        return False

    def _extraction_fetch_url(
        self,
        url: str,
        params: dict[str, typing.Any] | None = None,
        headers: dict[str, typing.Any] | None = None,
        data: dict | None = None,
        method: typing.Literal["get", "post"] = "get",
        timeout: int = 30,
        file_extension: str = "json",
    ) -> bool:
        if method == "get":
            response = requests.get(url, params=params, headers=headers, timeout=timeout, proxies=self.proxies)
        elif method == "post":
            response = requests.post(url, headers=headers, data=data, timeout=timeout, proxies=self.proxies)
        else:
            typing.assert_never(method)

        if response.status_code == 404:
            logger.warning(
                "The requested url not found",
                extra=log_extra({"url": url, "source": self.source_enum}),
                exc_info=True,
            )

        # NOTE: Handle Ratelimit manually
        if response.status_code in self.RETRY_STATUS_CODE:
            retry_after = response.headers.get("Retry-After", None)
            retry_after = retry_after and int(retry_after)
            raise RateLimitError(retry_after=retry_after)

        response.raise_for_status()
        self.extraction_object.resp_code = response.status_code

        if response.status_code in [200, 204]:
            response_data = self._extraction_store_data(
                extraction_object=self.extraction_object,
                response=response,
                file_extension=file_extension,
            )
            # Check if response contains data
            if response_data:
                logger.info("Data extracted successfully")
                return True
            logger.warning("No data found in response")
        return False

    @classmethod
    def init_extraction(
        cls,
        *,
        metadata: ExtractionMetadataTypeVar,
        parent_extraction: ExtractionData | None = None,
        add_to_queue: bool = True,
        queue_name: str | None = None,
    ) -> ExtractionData:
        extraction_obj = ExtractionData.objects.create(
            source=cls.source_enum,
            url=metadata.url,  # type: ignore[reportAttributeAccessIssue] TODO
            status=ExtractionData.Status.PENDING,
            source_validation_status=ExtractionData.ValidationStatus.NO_VALIDATION,
            trace_id=get_trace_id(parent_extraction),
            parent=parent_extraction,
            metadata=metadata.model_dump(),
            attempt_no=0,
            resp_code=0,
        )

        if add_to_queue:
            cls.task.apply_async([extraction_obj.pk], queue=queue_name or cls.DEFAULT_CELERY_QUEUE)
        return extraction_obj

    @abc.abstractmethod
    def handle_extract(self):
        raise NotImplementedError()

    def handle_extract_error(self, exc: Exception):
        if isinstance(exc, NoDataException):
            logger.warning("NoDataException raised for extraction %s", self.extraction_object.pk)
            self.extraction_object.source_validation_status = ExtractionData.ValidationStatus.NO_DATA
            self.extraction_object.mark_as_ended(ExtractionData.Status.SUCCESS)
            return

        # Retry Exception
        retries = self.celery_task.request.retries
        if isinstance(exc, RateLimitError):
            if retries >= self.MAX_RATE_LIMIT_RETRY_LIMIT:
                logger.warning("Max retries reached for request error.")
                self.extraction_object.mark_as_ended(ExtractionData.Status.FAILED)
                return

            if exc.retry_after:
                try:
                    delay = max(self.MIN_RETRY_DELAY, int(exc.retry_after))
                    logger.warning(f"Rate limited! Using Retry-After header: retrying in {delay:.2f} seconds.")
                except ValueError:
                    delay = self.celery_task.exponential_backoff_with_jitter(
                        retries,
                        min_delay=self.MIN_RETRY_DELAY,
                        max_delay=self.MAX_RETRY_DELAY,
                    )
                    logger.warning(f"Invalid Retry-After value. Falling back to backoff: retrying in {delay:.2f} seconds.")
            else:
                delay = self.celery_task.exponential_backoff_with_jitter(
                    retries,
                    min_delay=self.MIN_RETRY_DELAY,
                    max_delay=self.MAX_RETRY_DELAY,
                )
                logger.warning(f"Rate limited. Retrying in {delay:.2f} seconds (backoff).")

        elif isinstance(exc, requests.exceptions.RequestException):
            if retries >= self.MAX_RETRY_LIMIT:
                logger.warning("Max retries reached for request error.")
                self.extraction_object.mark_as_ended(ExtractionData.Status.FAILED)
                return

            # Fewer retries for generic request exceptions
            delay = self.celery_task.exponential_backoff_with_jitter(
                retries,
                min_delay=self.MIN_RETRY_DELAY,
                max_delay=self.MAX_RETRY_DELAY,
            )
            logger.warning(
                f"Rate limited. Retrying in {delay:.2f} seconds (backoff).",
                extra=log_extra({"source": self.extraction_object.source}),
                exc_info=True,
            )

        else:
            self.extraction_object.mark_as_ended(ExtractionData.Status.FAILED)

            raise exc

        self.extraction_object.mark_as_ended(ExtractionData.Status.ON_RETRY)
        # Increment attempt_no
        ExtractionData.objects.filter(pk=self.extraction_object.pk).update(attempt_no=models.F("attempt_no") + 1)
        raise self.celery_task.retry(exc=exc, countdown=delay)

    def handle(self):
        self.extraction_object.mark_as_started()
        try:
            resp = self.handle_extract()
            self.extraction_object.mark_as_ended(ExtractionData.Status.SUCCESS)
            return resp
        except Exception as exc:
            # NOTE: handle_extract_error only handles known errors, others are re-raised
            return self.handle_extract_error(exc)

    # FIXME: Implement init subclass to check if abstract methods are implemented on subclasses
    @staticmethod
    @abc.abstractmethod
    @app.task()
    def task(celery_task: RetryableTask, extraction_id: int) -> None:
        """
        Not NotImplemented due to celery limitation with classmethod. Eg:

        @app.task(bind=True, base=RetryableTask)
        def task(celery_task, extraction_id):
            return XYZExtraction(celery_task, extraction_id).handle()

        """
        raise NotImplementedError()
