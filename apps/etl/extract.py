import requests
from celery.utils.log import get_task_logger
from django.core.exceptions import ObjectDoesNotExist

from .models import ExtractionData

logger = get_task_logger(__name__)


class Extraction:
    def __init__(self, url: str):
        self.url = url

    def _get_file_extension(self, content_type):
        mappings = {
            "application/json": "json",
            "text/html": "html",
            "application/xml": "xml",
            "text/csv": "csv",
        }
        return mappings.get(content_type, "txt")

    def pull_data(self, source: int, retry_count: int, timeout: int = 30, ext_object_id: int = None):
        resp_status = ExtractionData.Status.IN_PROGRESS
        source_validation_status = ExtractionData.ValidationStatus.NO_VALIDATION

        # Update extraction object status to in_progress
        if ext_object_id:
            try:
                instance_obj = ExtractionData.objects.get(id=ext_object_id)
                instance_obj.resp_code = resp_status
                instance_obj.attempt_no = retry_count
                instance_obj.save(update_fields=["resp_code", "attempt_no"])
            except ExtractionData.DoesNotExist:
                raise ObjectDoesNotExist("ExtractionData object with ID {ext_object_id} not found")

        try:
            response = requests.get(self.url, timeout=timeout)
            resp_type = response.headers.get("Content-Type", "")
            file_extension = self._get_file_extension(resp_type)

            # Try saving the data in case of failure
            if response.status_code != 200:
                data = {
                    "source": source,
                    "url": self.url,
                    "attempt_no": retry_count,
                    "resp_code": response.status_code,
                    "status": ExtractionData.Status.FAILED,
                    "resp_data": None,
                    "resp_data_type": "text",
                    "file_extension": None,
                    "source_validation_status": ExtractionData.ValidationStatus.NO_VALIDATION,
                    "content_validation": "",
                    "resp_text": response.text,
                }
                if response.status_code == 204:
                    data["source_validation_status"] = ExtractionData.ValidationStatus.NO_DATA
                    source_validation_status = ExtractionData.ValidationStatus.NO_DATA

                for key, value in data.items():
                    setattr(instance_obj, key, value)
                instance_obj.save()

                if not response.status_code == 204:  # bypass exception when content is empty
                    logger.error(f"Request failed with status {response.status_code}")
                    raise Exception("Request failed")

            resp_status = ExtractionData.Status.SUCCESS

            return {
                "source": source,
                "url": self.url,
                "attempt_no": retry_count,
                "resp_code": response.status_code,
                "status": resp_status,
                "resp_data": response,
                "resp_data_type": resp_type,
                "file_extension": file_extension,
                "source_validation_status": source_validation_status,
                "content_validation": "",
                "resp_text": "",
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"Extraction failed for source {source}: {str(e)}")
            raise Exception(f"Request failed: {e}")
