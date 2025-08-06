import json
from unittest.mock import MagicMock, patch

import json5
import pytest
import requests
from django.conf import settings
from django.core.serializers import serialize
from django.test import override_settings
from pystac_monty.sources.common import MontyDataTransformer

from apps.etl.etl_tasks.gfd import ext_and_transform_gfd_historical_data
from apps.etl.models import ExtractionData, PyStacLoadData, Transform
from apps.etl.utils import remove_ignored_keys
from main.configs import etl_config

# Set base_collection_url
MontyDataTransformer.base_collection_url = settings.BASE_DIR / "libs/pystac-monty/monty-stac-extension/examples"

# Test cases using JSON5
TEST_CASES = [
    {
        "input": "gfd.json5",
        "output": "output_gfd.json",
        "expected": "fixed_output_gfd.json",
    },
]


@pytest.mark.django_db
@pytest.mark.parametrize("case", TEST_CASES)
@override_settings(
    TRANSFORM_SUCCESS_RATE=20,
    CELERY_TASK_ALWAYS_EAGER=True,
)
def test_handle_extraction_various_gfd_files(case):
    input_filename = case["input"]
    fixed_filename = case["expected"]

    # Path to input JSON5 file
    input_path = settings.BASE_DIR / "apps/etl/tests/dataset/gfd" / input_filename

    # Load mock data from JSON5
    with open(input_path, "r", encoding="utf-8") as f:
        mock_data = json5.load(f)

    # Patch the internal method to return mock data
    with patch("apps.etl.extraction.sources.gfd.extract.GFDExtraction._get_flood_data", return_value=mock_data):
        ext_and_transform_gfd_historical_data()

    # Assertions for DB objects
    assert ExtractionData.objects.count() == 1
    assert Transform.objects.count() == 1
    assert PyStacLoadData.objects.count() == 8

    # Path for expected (fixed) JSON output
    expected_output_path = settings.BASE_DIR / "apps/etl/tests/dataset/gfd" / fixed_filename
    assert expected_output_path.exists(), f"Expected reference file {expected_output_path} does not exist."

    # Load actual serialized DB output
    latest_data = PyStacLoadData.objects.all()
    latest_data_json = serialize("json", latest_data)
    actual_json = json.loads(latest_data_json)

    # Load expected output
    with open(expected_output_path, "r", encoding="utf-8") as expected_file:
        expected_json = json5.load(expected_file)

    # Keys to ignore when comparing
    ignored_keys = {"created_at", "modified_at", "monty:etl_id", "pk", "trace", "transform_id", "href"}

    # Clean and compare
    filtered_actual = remove_ignored_keys(actual_json, ignored_keys)
    filtered_expected = remove_ignored_keys(expected_json, ignored_keys)

    assert filtered_actual == filtered_expected, f"Differences found when comparing to fixed file {fixed_filename}."
