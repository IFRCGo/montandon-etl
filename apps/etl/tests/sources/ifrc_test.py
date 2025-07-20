import json
from unittest.mock import MagicMock, patch

import json5
import pytest
import requests
from django.conf import settings
from django.core.serializers import serialize
from django.test import override_settings
from pystac_monty.sources.common import MontyDataTransformer

from apps.etl.etl_tasks.ifrc_event import ext_and_transform_ifrcevent_latest_data
from apps.etl.models import ExtractionData, PyStacLoadData, Transform
from apps.etl.utils import remove_ignored_keys
from main.configs import etl_config

# Set base_collection_url
MontyDataTransformer.base_collection_url = settings.BASE_DIR / "libs/pystac-monty/monty-stac-extension/examples"

# Define test cases
TEST_CASES = [
    {
        "input": "ifrc.json5",
        "output": "output_ifrc.json",  # not used for writing anymore, only used in logs
        "expected": "fixed_output_ifrc.json",
    },
]


@pytest.mark.django_db
@pytest.mark.parametrize("case", TEST_CASES)
@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
def test_handle_extraction_various_ifrc_files(case):
    input_filename = case["input"]
    fixed_filename = case["expected"]

    # Path to input JSON5 file
    input_path = settings.BASE_DIR / "apps/etl/tests/dataset/ifrc" / input_filename

    # Load mock data from JSON5
    with open(input_path, "r", encoding="utf-8") as f:
        mock_data = json5.load(f)

    # URL pattern to intercept
    def is_ifrc_url(url):
        return "appeal_type" in url and etl_config.IFRC_DATA_URL in url

    # Save original requests.get
    original_get = requests.get

    def custom_get(url, *args, **kwargs):
        if is_ifrc_url(url):
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_data
            mock_response.content = json.dumps(mock_data).encode("utf-8")
            mock_response.headers = {"Content-Type": "application/json"}
            return mock_response
        return original_get(url, *args, **kwargs)

    # Patch requests.get
    with patch("requests.get", side_effect=custom_get):
        # Run ETL
        ext_and_transform_ifrcevent_latest_data()

    # Assertions
    assert ExtractionData.objects.count() == 67
    assert Transform.objects.count() == 66
    assert PyStacLoadData.objects.count() == 65

    # Path for expected (fixed) JSON output
    expected_output_path = settings.BASE_DIR / "apps/etl/tests/dataset/ifrc" / fixed_filename
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
