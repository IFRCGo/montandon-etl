import requests

from .models import ExtractionData


class Extraction:
    def __init__(self, url: str):
        self.url = url

    def pull_data(self, retry_count, source: int, attempt_no: int = 1, timeout: int = 30):
        response = requests.get(self.url, timeout=timeout)
        resp_type = response.headers.get("Content-Type", "")
        file_extension = "txt"
        resp_data = response
        resp_status = ExtractionData.Status.IN_PROGRESS
        source_validation_status = ExtractionData.ValidationStatus.NO_VALIDATION

        if retry_count < 4:
            if response.status_code == 200:
                if "application/json" in resp_type:
                    file_extension = "json"
                    resp_type = resp_type
                if "text/html" in resp_type:
                    file_extension = "html"
                    resp_type = resp_type

                # if "application/json" in resp_type:
                #     print("Inside geo json")
                #     file_extension = "json"
                # elif "text/csv" in resp_type or "application/csv" in resp_type:
                #     file_extension = "csv"
                # elif "application/xml" in resp_type or "text/xml" in resp_type:
                #     file_extension = "xml"
                #     resp_data = response.text
                # elif "application/pdf" in resp_type:
                #     file_extension = "pdf"
                # elif "text/plain" in resp_type:
                #     file_extension = "txt"
                #     resp_data = response.text

                return {
                    "source": source,
                    "url": self.url,
                    "attempt_no": attempt_no,
                    "resp_code": response.status_code,
                    "status": ExtractionData.Status.SUCCESS,
                    "resp_data": resp_data,
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
                "resp_data": response,
                "resp_data_type": "",
                "file_extension": None,
                "content_validation": "",
                "resp_text": resp_data.text,
            }
