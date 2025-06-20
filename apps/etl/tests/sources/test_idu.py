import json
import json5
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from django.core.serializers import serialize
from django.test import override_settings
from django.conf import settings

import requests
from apps.etl.etl_tasks.idu import ext_and_transform_idu_latest_data
from apps.etl.models import ExtractionData, Transform, PyStacLoadData
from pystac_monty.sources.common import MontyDataTransformer
from main.configs import etl_config

# Set base_collection_url
MontyDataTransformer.base_collection_url = settings.BASE_DIR / "libs/pystac-monty/monty-stac-extension/examples"

# Test cases using JSON5 as it allows comments to be added to the json file
TEST_CASES = [
    {
        "input": "idus.json5",
        "output": "output_idu.json",
        "expected": "fixed_output_idu.json"
    },
]

def remove_ignored_keys(obj, keys_to_ignore):
    """
    Recursively remove keys from dicts if the key is in keys_to_ignore.
    Works on nested dicts and lists.
    """
    if isinstance(obj, dict):
        for key in list(obj.keys()):
            if key in keys_to_ignore:
                obj.pop(key)
            else:
                remove_ignored_keys(obj[key], keys_to_ignore)
    elif isinstance(obj, list):
        for item in obj:
            remove_ignored_keys(item, keys_to_ignore)
    return obj


@pytest.mark.django_db
@pytest.mark.parametrize("case", TEST_CASES)
@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
def test_handle_extraction_various_idu_files(case):
    input_filename = case["input"]
    output_filename = case["output"]
    fixed_filename = case["expected"]

    # Path to input JSON5 file
    input_path = settings.BASE_DIR / 'apps/etl/Dataset/IDMC-IDU' / input_filename

    # Load mock data from JSON5
    with open(input_path, 'r', encoding='utf-8') as f:
        mock_data = json5.load(f)

    # URL to intercept
    source_url = f"{etl_config.IDMC_DATA_URL}/external-api/idus/last-180-days/"

    # Save original requests.get to call for other URLs
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
    with patch('requests.get', side_effect=custom_get):
        # Run ETL extraction and transformation task
        ext_and_transform_idu_latest_data()

    # Define output directory and ensure it exists
    output_dir = settings.BASE_DIR / "output/IDU_Output/"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / output_filename

    # Serialize queryset to JSON string
    latest_data = PyStacLoadData.objects.all()
    latest_data_json = serialize('json', latest_data)

    # Write serialized JSON to output file
    with open(output_path, 'w', encoding='utf-8') as json_file:
        json_file.write(latest_data_json)

    # Assertions for outputs and database entries
    assert output_path.exists(), f"Expected output file {output_path} was not created."
    assert ExtractionData.objects.count() == 1
    assert Transform.objects.count() == 1
    assert PyStacLoadData.objects.count() == 23

    # Path for expected (fixed) JSON output
    expected_output_path = settings.BASE_DIR / "output/IDU_Output" / fixed_filename
    assert expected_output_path.exists(), f"Expected reference file {expected_output_path} does not exist."

    # Load actual and expected JSON for comparison
    with open(output_path, 'r', encoding='utf-8') as actual_file:
        actual_json = json5.load(actual_file)

    with open(expected_output_path, 'r', encoding='utf-8') as expected_file:
        expected_json = json5.load(expected_file)

    # Keys to ignore anywhere in JSON
    ignored_keys = {"created_at", "modified_at", "monty:etl_id"}

    # Remove ignored keys from both JSONs before comparison
    filtered_actual = remove_ignored_keys(actual_json, ignored_keys)
    filtered_expected = remove_ignored_keys(expected_json, ignored_keys)

    # Assert equality of filtered JSON objects
    assert filtered_actual == filtered_expected, f"Differences found when comparing to fixed file {fixed_filename}."
