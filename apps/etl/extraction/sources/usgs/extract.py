import json
import logging
import typing
from datetime import datetime, timedelta
from enum import Enum

import pydantic
import requests
from celery import chord

from apps.etl.extraction.sources.base.handler import BaseExtractionV2
from apps.etl.models import ExtractionData
from apps.etl.transform.sources.usgs import USGSTransformHandler
from main.celery import CeleryQueue, app
from utils.celery import RetryableTask
from utils.requests import RateLimitError
import random
logger = logging.getLogger(__name__)


class USGSExtractionMetadataType(str, Enum):
    QUERY = "QUERY"
    DETAIL = "DETAIL"
    LOSSE = "LOSSE"
    RESPONSE_EXCEEDED = "RESPONSE_EXCEEDED"


class USGSExtractionMetadata(pydantic.BaseModel):
    url: str
    type: USGSExtractionMetadataType


class USGSExtraction(BaseExtractionV2[USGSExtractionMetadata]):
    """
    Handles data extraction from the USGS API
    """

    MIN_RETRY_DELAY = 60 * 5
    MAX_RETRY_DELAY = 60 * 10

    source_enum = ExtractionData.Source.USGS
    extraction_metadata_class = USGSExtractionMetadata

    def __init__(self, task, extraction_id, queue_name=None):
        super().__init__(task, extraction_id)
        self.queue_name = queue_name  

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
        
        queue_proxy_map: dict = {
            CeleryQueue.USGS_EXTRACTION_1: "socks5h://192.168.88.28:1081",
            CeleryQueue.USGS_EXTRACTION_2: "socks5h://192.168.88.28:1082",
            CeleryQueue.USGS_EXTRACTION_3: "socks5h://192.168.88.28:1083",
            CeleryQueue.USGS_EXTRACTION_4: "socks5h://192.168.88.28:1084",

        }

        proxy = queue_proxy_map.get(self.queue_name, "socks5h://192.168.88.28:1081")

        proxies = {
            "http": proxy,
            "https": proxy,
        }

        if method == "get":
            response = requests.get(url, params=params, headers=headers, timeout=timeout, proxies= proxies)
        elif method == "post":
            response = requests.post(url, headers=headers, data=data, timeout=timeout)
        else:
            typing.assert_never(method)

        # NOTE: Handle Ratelimit manually
        if response.status_code in self.RETRY_STATUS_CODE:
            retry_after = response.headers.get("Retry-After", None)
            retry_after = retry_after and int(retry_after)
            raise RateLimitError(retry_after=retry_after)

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

    def handle_type_query(self):
        # Handles base extraction from the all day url
        self._extraction_fetch_url(
            self.extraction_metadata.url,
            headers={"Content-Type": "application/json"},
        )

        if self.extraction_object.resp_code == 400:
            return self.handle_response_exceeded()

        # FIXME: Handle error?
        response_data = json.loads(self.extraction_object.resp_data.read())
        # FIXME: We might need to write a simple validator here
        features_list = response_data["features"]

        for feature_item in features_list:
            if "detail" not in feature_item["properties"]:
                continue
            detail_url = feature_item["properties"]["detail"]
            self.init_extraction(
                metadata=USGSExtractionMetadata(
                    url=detail_url,
                    type=USGSExtractionMetadataType.DETAIL,
                ),
                parent_extraction=self.extraction_object,
                queue_name= self.queue_name
            )

    def handle_type_detail(self):
        self._extraction_fetch_url(self.extraction_metadata.url)

        with self.extraction_object.resp_data.open() as file_data:
            detail_data = json.loads(file_data.read())

        losses_tasks = []
        if "losspager" in detail_data["properties"]["products"]:
            for item in detail_data["properties"]["products"]["losspager"]:
                if "json/losses.json" in item["contents"]:
                    url = item["contents"]["json/losses.json"]["url"]
                    losses_extraction_obj = self.init_extraction(
                        metadata=USGSExtractionMetadata(
                            url=url,
                            type=USGSExtractionMetadataType.LOSSE,
                        ),
                        parent_extraction=self.extraction_object,
                        add_to_queue=False,
                    )
                    losses_tasks.append(
                        USGSExtraction.task.si(losses_extraction_obj.pk).set(queue=self.queue_name)
                    )


        if losses_tasks:
            chord(
                losses_tasks,
                # NOTE: After all losses_tasks are done, then USGSTransformHandler is called by celery
                USGSTransformHandler.task.si(self.extraction_object.pk),
            ).apply_async()
        else:
            # TODO: Or raise NoDataException()?
            USGSTransformHandler.task.delay(self.extraction_object.pk)

    def handle_type_losse(self):
        self._extraction_fetch_url(self.extraction_metadata.url)

    def handle_response_exceeded(self):
        self.extraction_object.metadata["type"] = USGSExtractionMetadataType.RESPONSE_EXCEEDED
        self.extraction_object.save()
        url = self.extraction_metadata.url
        try:
            start_date_str = url.split("starttime=")[1].split("&")[0]
            end_date_str = url.split("endtime=")[1].split("&")[0]
        except IndexError as error:
            logger.error(f"Error: {error}", exc_info=True, extra={"source": "USGS"})
            return False

        start_date_obj = datetime.strptime(start_date_str, "%Y-%m-%d")
        end_date_obj = datetime.strptime(end_date_str, "%Y-%m-%d")
        mid_date_obj = start_date_obj + (end_date_obj - start_date_obj) / 2
        mid_date_str = mid_date_obj.strftime("%Y-%m-%d")
        second_half_start_str = (mid_date_obj + timedelta()).strftime("%Y-%m-%d")

        first_half_url = url.replace(f"endtime={end_date_str}", f"endtime={mid_date_str}")

        self.init_extraction(
            metadata=USGSExtractionMetadata(
                url=first_half_url,
                type=USGSExtractionMetadataType.QUERY,
            ),
        )

        second_half_url = url.replace(f"starttime={start_date_str}", f"starttime={second_half_start_str}")

        self.init_extraction(
            metadata=USGSExtractionMetadata(
                url=second_half_url,
                type=USGSExtractionMetadataType.QUERY,
            ),
        )

    def handle_extract(self):
        handler_type = self.extraction_metadata.type
        logger.info(f"Starting extraction<{self.extraction_object.pk}> with metadata: {self.extraction_metadata}")
        match handler_type:
            case USGSExtractionMetadataType.QUERY:
                return self.handle_type_query()
            case USGSExtractionMetadataType.DETAIL:
                return self.handle_type_detail()
            case USGSExtractionMetadataType.LOSSE:
                return self.handle_type_losse()
            case USGSExtractionMetadataType.RESPONSE_EXCEEDED:
                return self.handle_response_exceeded()
            case _:
                typing.assert_never(handler_type)

    @staticmethod
    @app.task(
        bind=True,
        base=RetryableTask,
        queue=CeleryQueue.USGS_EXTRACTION,
        rate_limit="100/m",  # limit is 500 requests per 5 minute window
    )
    def task(celery_task, extraction_id):
        queue_name = getattr(celery_task.request, 'delivery_info', {}).get('routing_key')
        USGSExtraction(celery_task, extraction_id, queue_name=queue_name).handle()
