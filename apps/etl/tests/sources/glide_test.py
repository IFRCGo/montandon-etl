import json
from unittest.mock import MagicMock, patch

import json5
import pytest
import requests
from django.conf import settings
from django.core.serializers import serialize
from django.test import override_settings
from pystac_monty.sources.common import MontyDataTransformer

from apps.etl.etl_tasks.glide import ext_and_transform_glide_latest_data
from apps.etl.models import ExtractionData, PyStacLoadData, Transform
from apps.etl.tests.common.base_settings_test import TEST_CACHES
from apps.etl.utils import remove_ignored_keys
from main.configs import etl_config

# Set base_collection_url
MontyDataTransformer.base_collection_url = settings.BASE_DIR / "libs/pystac-monty/monty-stac-extension/examples"

# Test cases using JSON5 as it allows comments to be added to the json file
TEST_CASES = [
    {
        "input": "glide.json5",
        "output": "output_glide.json",  # only used in logs
        "expected": "fixed_output_glide.json",
    },
]


@pytest.mark.django_db
@pytest.mark.parametrize("case", TEST_CASES)
@override_settings(TRANSFORM_SUCCESS_RATE=20, CELERY_TASK_ALWAYS_EAGER=True, CACHES=TEST_CACHES)
def test_handle_extraction_various_glide_files(case):
    input_filename = case["input"]
    fixed_filename = case["expected"]

    # Path to input JSON5 file
    input_path = settings.BASE_DIR / "apps/etl/tests/dataset/glide" / input_filename

    # Load mock data from JSON5
    with open(input_path, "r", encoding="utf-8") as f:
        mock_data = json5.load(f)

    # URL to intercept for GIDD
    source_url = f"{etl_config.GLIDE_URL}/glide/jsonglideset.jsp"
    # Save original requests.get to allow passthrough for other URLs
    original_get = requests.get

    def custom_get(url, *args, **kwargs):
        if url == source_url:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_data
            mock_response.content = json.dumps(mock_data).encode("utf-8")
            mock_response.headers = {"Content-Type": "application/json"}
            return mock_response
        else:
            return original_get(url, *args, **kwargs)

    # Patch requests.get to use our mock
    with patch("requests.get", side_effect=custom_get):
        # Run ETL task for GIDD
        ext_and_transform_glide_latest_data()

    # Assertions for DB objects
    assert ExtractionData.objects.count() == 25
    assert Transform.objects.count() == 25
    assert PyStacLoadData.objects.count() == 150

    # Path for expected (fixed) JSON output
    expected_output_path = settings.BASE_DIR / "apps/etl/tests/dataset/glide" / fixed_filename
    assert expected_output_path.exists(), f"Expected reference file {expected_output_path} does not exist."

    # Load actual serialized DB output
    latest_data = PyStacLoadData.objects.all()
    latest_data_json = serialize("json", latest_data)
    actual_json = json.loads(latest_data_json)

    # Load expected output
    with open(expected_output_path, "r", encoding="utf-8") as expected_file:
        expected_json = json.load(expected_file)

    # Keys to ignore when comparing
    ignored_keys = {"created_at", "modified_at", "monty:etl_id", "pk", "trace", "transform_id", "href", "keywords"}

    # Clean and compare
    filtered_actual = remove_ignored_keys(actual_json, ignored_keys)
    filtered_expected = remove_ignored_keys(expected_json, ignored_keys)

    assert filtered_actual == filtered_expected, f"Differences found when comparing to fixed file {fixed_filename}."
