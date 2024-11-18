import json
import requests
from datetime import timedelta, time
from django.utils import timezone

from .models import ExtractionLog


class Extraction:
    def __init__(self, url: str):
        self.url = url

    def calculate_res_time(self, starttime, endtime):
        # Ensure the times are set
        if starttime and endtime:
            delta = endtime - starttime
            # Convert timedelta to time
            total_seconds = int(delta.total_seconds())
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            return time(hour=hours % 24, minute=minutes, second=seconds)  # Ensure it's within 24 hours
        return None

    def pull_data(self, source: str, attempt_no: int=1, timeout: int=30):
        start_time = timezone.now()
        response = requests.get(self.url, timeout=timeout)
        end_time = timezone.now()
        if response.status_code == 200:
            return {
                "source": source,
                "url": self.url,
                "attempt_no": attempt_no,
                "req_started_datetime": start_time,
                "response_time": self.calculate_res_time(start_time, end_time),
                "response_code": response.status_code,
                "raw_data": json.dumps(response.json()),
                "status": ExtractionLog.Status.SUCCESS
            }
        return {
            "source": source,
            "url": self.url,
            "attempt_no": attempt_no,
            "req_started_datetime": start_time,
            "response_time": self.calculate_res_time(start_time, end_time),
            # "response_time": (end_time - start_time).time(),
            "response_code": response.status_code,
            "raw_data": json.dumps({}),
            "status": ExtractionLog.Status.FAILED
        }
