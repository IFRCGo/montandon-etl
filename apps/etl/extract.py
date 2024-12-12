import requests

from .models import ExtractionData


class Extraction:
    def __init__(self, url: str):
        self.url = url

    def pull_data(self, source: int, retry_count: int, attempt_no: int = 1, timeout: int = 30):
        file_extension = "txt"
        resp_status = ExtractionData.Status.IN_PROGRESS
        source_validation_status = ExtractionData.ValidationStatus.NO_VALIDATION

        try:
            response = requests.get(self.url, timeout=timeout)
            resp_type = response.headers.get("Content-Type", "")

            if retry_count < 4:
                if response.status_code == 200:
                    if "application/json" in resp_type:
                        file_extension = "json"
                        resp_type = resp_type
                    if "text/html" in resp_type:
                        file_extension = "html"
                        resp_type = resp_type

                    return {
                        "source": source,
                        "url": self.url,
                        "attempt_no": retry_count,
                        "resp_code": 200,
                        "status": ExtractionData.Status.SUCCESS,
                        "resp_data": response,
                        "resp_data_type": resp_type,
                        "file_extension": file_extension,
                        "source_validation_status": ExtractionData.ValidationStatus.NO_VALIDATION,
                        "content_validation": "",
                        "resp_text": "",
                    }
                else:
                    raise Exception()
            else:
                if response.status_code == 204:
                    resp_status = ExtractionData.Status.SUCCESS
                    source_validation_status = ExtractionData.ValidationStatus.NO_DATA
                elif response.status_code == 500:
                    resp_status = ExtractionData.Status.FAILED
                    source_validation_status = ExtractionData.ValidationStatus.NO_DATA

                return {
                    "source": source,
                    "url": self.url,
                    "attempt_no": attempt_no,
                    "resp_code": response.status_code,
                    "status": resp_status,
                    "source_validation_status": source_validation_status,
                    "resp_data": None,
                    "resp_data_type": "",
                    "file_extension": None,
                    "content_validation": "",
                    "resp_text": response.text,
                }
        except requests.exceptions.RequestException as e:
            return {
                "source": source,
                "url": self.url,
                "attempt_no": attempt_no,
                "resp_code": 0,
                "status": ExtractionData.Status.FAILED,
                "source_validation_status": source_validation_status,
                "resp_data": None,
                "resp_data_type": "",
                "file_extension": None,
                "content_validation": "",
                "resp_text": str(e),
            }
