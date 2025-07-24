import abc
import logging
import typing
from typing import Optional

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


ExtractionMetadataTypeVar = typing.TypeVar("ExtractionMetadataTypeVar", bound=pydantic.BaseModel)


class BaseExtractionV2(typing.Generic[ExtractionMetadataTypeVar]):
    MAX_RETRY_LIMIT = 3
    MAX_RATE_LIMIT_RETRY_LIMIT = 10
    MIN_RETRY_DELAY = 30
    MAX_RETRY_DELAY = 60
    RETRY_STATUS_CODE = [403, 429]
    DEFAULT_CELERY_QUEUE = CeleryQueue.DEFAULT

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

    def _extraction_fetch_graphql(self, url: str, payload: dict, headers: Optional[dict] = None, timeout: int = 30) -> bool:
        if not payload or "query" not in payload:
            return False
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=timeout, proxies=self.proxies)
        except requests.exceptions.Timeout as e:
            logger.error("Request timed out", exc_info=True, extra=log_extra({"source": self.extraction_object.source}))
            raise e

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
        try:
            if method == "get":
                response = requests.get(url, params=params, headers=headers, timeout=timeout, proxies=self.proxies)
            elif method == "post":
                response = requests.post(url, headers=headers, data=data, timeout=timeout, proxies=self.proxies)
            else:
                typing.assert_never(method)
        except requests.exceptions.Timeout as e:
            logger.warning(
                "Request timed out",
                extra=log_extra({"url": url, "source": self.source_enum}),
            )
            raise e

        if response.status_code == 404:
            logger.error(
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
            cls.task.apply_async(extraction_obj.pk, queue=queue_name or cls.DEFAULT_CELERY_QUEUE)
        return extraction_obj

    @abc.abstractmethod
    def handle_extract(self, retrigger: bool):
        raise NotImplementedError()

    def handle_extract_error(self, exc: Exception):
        if isinstance(exc, NoDataException):
            logger.warning("NoDataException raised for extraction %s", self.extraction_object.pk)
            self.extraction_object.source_validation_status = ExtractionData.ValidationStatus.NO_DATA
            self.extraction_object.mark_as_ended(ExtractionData.Status.SUCCESS)
            return

        # Retry Exception
        retries = self.celery_task.request.retries

        if retries >= self.MAX_RETRY_LIMIT:
            logger.warning("Max retries reached for request error.")
            self.extraction_object.mark_as_ended(ExtractionData.Status.FAILED)
            return

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

    def handle(self, retrigger: bool = False):
        self.extraction_object.mark_as_started()
        try:
            resp = self.handle_extract(retrigger=retrigger)
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
