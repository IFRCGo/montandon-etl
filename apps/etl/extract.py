import requests
from django.core.exceptions import ObjectDoesNotExist

from .models import ExtractionData


class Extraction:
    def __init__(self, url: str):
        self.url = url

    def _get_file_extension(self, content_type):
        if "application/json" in content_type:
            return "json"
        elif "text/html" in content_type:
            return "html"
        return "txt"

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

                instance_obj = ExtractionData.objects.get(id=ext_object_id)
                for key, value in data.items():
                    setattr(instance_obj, key, value)
                instance_obj.save()

                raise Exception()

            elif response.status_code == 204:
                source_validation_status = ExtractionData.ValidationStatus.NO_DATA

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

        except Exception:
            raise Exception()
