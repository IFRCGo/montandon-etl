import json
from unittest.mock import MagicMock, patch

import json5
import pytest
import requests
from django.conf import settings
from django.core.serializers import serialize
from django.test import override_settings
from pystac_monty.sources.common import MontyDataTransformer

from apps.etl.etl_tasks.usgs import ext_and_transform_usgs_latest_data
from apps.etl.models import ExtractionData, PyStacLoadData, Transform
from apps.etl.utils import remove_ignored_keys

# Set base_collection_url
MontyDataTransformer.base_collection_url = settings.BASE_DIR / "libs/pystac-monty/monty-stac-extension/examples"

# Define test cases
TEST_CASES = [
    {
        "input": {"query": "usgs_all_day.geojson", "detail": "usgs_detail.json", "losses": "losses.json"},
        "output": "output_usgs.json",  # not used for writing anymore
        "expected": "fixed_output_usgs.json",
    },
    # Add more cases here as needed
]


@pytest.mark.django_db
@pytest.mark.parametrize("case", TEST_CASES)
@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
def test_handle_extraction_various_usgs_files(case):
    input_files = case["input"]
    fixed_filename = case["expected"]

    # Path to input files
    input_dir = settings.BASE_DIR / "apps/etl/tests/datasets/usgs"
    query_response = json.load(open(input_dir / input_files["query"], encoding="utf-8"))
    detail_response = json.load(open(input_dir / input_files["detail"], encoding="utf-8"))
    losses_response = json.load(open(input_dir / input_files["losses"], encoding="utf-8"))

    def is_usgs_url(url):
        return ("all_day" in url and "earthquakes" in url) or "detail" in url or "losses.json" in url

    real_requests_get = requests.get

    def custom_get(url, *args, **kwargs):
        if "all_day" in url:
            return _mock_response(query_response, content_type="application/geo+json")
        elif "detail" in url:
            return _mock_response(detail_response)
        elif "losses.json" in url:
            return _mock_response(losses_response)
        return real_requests_get(url, *args, **kwargs)

    # Patch requests.get
    with patch("requests.get", side_effect=custom_get):
        # Run ETL
        ext_and_transform_usgs_latest_data()

    # Assertions
    assert ExtractionData.objects.count() == 3
    assert Transform.objects.count() == 1
    assert PyStacLoadData.objects.count() == 2

    # Path for expected (fixed) JSON output
    expected_output_path = input_dir / fixed_filename
    assert expected_output_path.exists(), f"Expected reference file {expected_output_path} does not exist."

    # Load actual data
    latest_data = PyStacLoadData.objects.all()
    latest_data_json = serialize("json", latest_data)
    actual_json = json.loads(latest_data_json)

    # Load expected data
    with open(expected_output_path, "r", encoding="utf-8") as expected_file:
        expected_json = json5.load(expected_file)

    # Ignore unstable keys
    ignored_keys = {"created_at", "modified_at", "monty:etl_id"}

    filtered_actual = remove_ignored_keys(actual_json, ignored_keys)
    filtered_expected = remove_ignored_keys(expected_json, ignored_keys)

    assert filtered_actual == filtered_expected, f"Differences found when comparing to fixed file {fixed_filename}."


def _mock_response(json_data, content_type="application/json"):
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = json_data
    response.content = json.dumps(json_data).encode("utf-8")
    response.headers = {"Content-Type": content_type}
    return response
