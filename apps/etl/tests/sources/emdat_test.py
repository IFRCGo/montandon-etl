import copy
import json
from unittest.mock import MagicMock, patch

import json5
import pytest
import requests
from django.conf import settings
from django.core.serializers import serialize
from django.test import override_settings
from pystac_monty.sources.common import MontyDataTransformer

from apps.etl.etl_tasks.emdat import ext_and_transform_emdat_latest_data
from apps.etl.models import ExtractionData, PyStacLoadData, Transform
from apps.etl.tests.common.base_settings_test import TEST_CACHES
from apps.etl.utils import get_cluster_codes, remove_ignored_keys
from main.configs import etl_config

# Set base_collection_url
MontyDataTransformer.base_collection_url = settings.BASE_DIR / "libs/pystac-monty/monty-stac-extension/examples"

# Test cases
TEST_CASES = [
    {
        "input": "emdat.json5",
        "output": "output_emdat.json",
        "expected": "fixed_output_emdat.json",
    },
]


@pytest.mark.django_db
@pytest.mark.parametrize("case", TEST_CASES)
@override_settings(TRANSFORM_SUCCESS_RATE=20, CELERY_TASK_ALWAYS_EAGER=True, CACHES=TEST_CACHES)
def test_handle_extraction_various_emdat_files(case):
    input_filename = case["input"]
    fixed_filename = case["expected"]

    # Path to input JSON file
    input_path = settings.BASE_DIR / "apps/etl/tests/dataset/emdat" / input_filename

    # Load mock data
    with open(input_path, "r", encoding="utf-8") as f:
        mock_data = json5.load(f)

    # URL to intercept for EMDAT
    source_url = f"{etl_config.EMDAT_URL}/v1"

    # Save original requests.get
    original_get = requests.post

    def custom_get(url, *args, **kwargs):
        if url == source_url:
            # Filter the data based on the requested classification keys
            classif_keys = kwargs["json"]["variables"]["classif"]
            response_data = copy.deepcopy(mock_data)
            response_data["data"]["public_emdat"]["data"] = [
                record for record in mock_data["data"]["public_emdat"]["data"] if record["classif_key"] in classif_keys
            ]
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = response_data
            mock_response.content = json.dumps(response_data).encode("utf-8")
            mock_response.headers = {"Content-Type": "application/json"}
            return mock_response
        return original_get(url, *args, **kwargs)

    # Patch requests.get
    with patch("requests.post", side_effect=custom_get):
        ext_and_transform_emdat_latest_data()

    # Assertions
    # Single extraction for each classification key, transformed only for the keys having data
    assert ExtractionData.objects.count() == len(get_cluster_codes())
    assert Transform.objects.count() == 2
    assert PyStacLoadData.objects.count() == 28

    # Path for expected output
    expected_output_path = settings.BASE_DIR / "apps/etl/tests/dataset/emdat" / fixed_filename
    assert expected_output_path.exists(), f"Expected reference file {expected_output_path} does not exist."

    # Load actual DB output
    latest_data = PyStacLoadData.objects.all()
    latest_data_json = serialize("json", latest_data)
    actual_json = json.loads(latest_data_json)

    # Load expected output
    with open(expected_output_path, "r", encoding="utf-8") as expected_file:
        expected_json = json.load(expected_file)

    # Keys to ignore
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
        "processing:version",
        "processing:software",
    }

    # NOTE: Items are loaded from multiple extractions (one per classification key), so the order differs
    def sort_items(items):
        return sorted(items, key=lambda item: item["fields"]["item_id"])

    filtered_actual = sort_items(remove_ignored_keys(actual_json, ignored_keys))
    filtered_expected = sort_items(remove_ignored_keys(expected_json, ignored_keys))

    assert filtered_actual == filtered_expected, f"Differences found when comparing to fixed file {fixed_filename}."
