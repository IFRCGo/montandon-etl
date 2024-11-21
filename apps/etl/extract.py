import requests

from .models import ExtractionData


class Extraction:
    def __init__(self, url: str):
        self.url = url

    def pull_data(self, source: int, attempt_no: int = 1, timeout: int = 30):
        response = requests.get(self.url, timeout=timeout)
        resp_type = response.headers.get("Content-Type", "")
        file_extension = "txt"
        resp_data = response.content

        if response.status_code == 200:
            if "application/json" in resp_type:
                file_extension = "json"
                resp_type = ExtractionData.ResponseDataType.JSON
            elif "text/csv" in resp_type or "application/csv" in resp_type:
                file_extension = "csv"
                resp_type = ExtractionData.ResponseDataType.CSV
            elif "text/html" in resp_type:
                file_extension = "html"
                resp_type = ExtractionData.ResponseDataType.HTML
                resp_data = response.text
            elif "application/xml" in resp_type or "text/xml" in resp_type:
                file_extension = "xml"
                resp_type = ExtractionData.ResponseDataType.XML
                resp_data = response.text
            elif "application/pdf" in resp_type:
                file_extension = "pdf"
                resp_type = ExtractionData.ResponseDataType.PDF
            elif "text/plain" in resp_type:
                file_extension = "txt"
                resp_type = ExtractionData.ResponseDataType.TEXT
                resp_data = response.text

            return {
                "source": source,
                "url": self.url,
                "attempt_no": attempt_no,
                "resp_code": response.status_code,
                "status": ExtractionData.Status.SUCCESS,
                "resp_data": resp_data,
                "resp_type": resp_type,
                "file_extension": file_extension,
            }
        return {
            "source": source,
            "url": self.url,
            "attempt_no": attempt_no,
            "resp_code": response.status_code,
            "status": ExtractionData.Status.FAILED,
            "resp_data": None,
            "resp_type": None,
            "file_extension": None,
        }
