import json
from unittest.mock import MagicMock, patch

import pytest
import requests
from django.conf import settings
from django.core.serializers import serialize
from django.test import override_settings
from pystac_monty.sources.common import MontyDataTransformer

from apps.etl.etl_tasks.noaa_IBTrACS import ext_and_transform_ibtracs_latest_data
from apps.etl.models import ExtractionData, PyStacLoadData, Transform
from apps.etl.tests.common.base_settings_test import TEST_CACHES
from apps.etl.utils import remove_ignored_keys
from main.configs import etl_config

# Set base_collection_url
MontyDataTransformer.base_collection_url = settings.BASE_DIR / "libs/pystac-monty/monty-stac-extension/examples"

# Test cases
TEST_CASES = [
    {
        "input": "ibtracs.csv",
        "output": "output_ibtracs.json",
        "expected": "fixed_output_ibtracs.json",
    },
]


@pytest.mark.django_db
@pytest.mark.parametrize("case", TEST_CASES)
@override_settings(TRANSFORM_SUCCESS_RATE=20, CELERY_TASK_ALWAYS_EAGER=True, CACHES=TEST_CACHES)
def test_handle_extraction_various_ibtracs_files(case):
    input_filename = case["input"]
    fixed_filename = case["expected"]

    # Path to input CSV file
    input_path = settings.BASE_DIR / "apps/etl/tests/dataset/ibtracs" / input_filename

    # Load mock CSV content
    with open(input_path, "r", encoding="utf-8") as f:
        mock_csv_data = f.read()

    # URL to intercept
    source_url = (
        f"{etl_config.IBTRACS_DATA_URL}"
        "/data/international-best-track-archive-for-climate-stewardship-ibtracs/v04r01/access/csv/"
        + "ibtracs.ACTIVE.list.v04r01.csv"
    )

    original_get = requests.get

    def custom_get(url, *args, **kwargs):
        if url == source_url:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = mock_csv_data
            mock_response.content = mock_csv_data.encode("utf-8")
            mock_response.headers = {"Content-Type": "text/csv"}
            return mock_response
        return original_get(url, *args, **kwargs)

    # Patch requests.get
    with patch("requests.get", side_effect=custom_get):
        ext_and_transform_ibtracs_latest_data()

    # Assertions
    assert ExtractionData.objects.count() == 1
    assert Transform.objects.count() == 1
    assert PyStacLoadData.objects.count() == 10

    # Load actual output
    latest_data = PyStacLoadData.objects.all()
    latest_data_json = serialize("json", latest_data)
    actual_json = json.loads(latest_data_json)

    # Load expected output
    expected_output_path = settings.BASE_DIR / "apps/etl/tests/dataset/ibtracs" / fixed_filename
    assert expected_output_path.exists(), f"Expected reference file {expected_output_path} does not exist."
    with open(expected_output_path, "r", encoding="utf-8") as expected_file:
        expected_json = json.load(expected_file)

    # Keys to ignore in comparison
    ignored_keys = {
        "created_at",
        "modified_at",
        "monty:etl_id",
        "pk",
        "trace",
        "transform_id",
        "href",
        "keywords",
        "links",
        "stac_extensions",
    }

    filtered_actual = remove_ignored_keys(actual_json, ignored_keys)
    filtered_expected = remove_ignored_keys(expected_json, ignored_keys)

    assert filtered_actual == filtered_expected, f"Differences found when comparing to fixed file {fixed_filename}."
