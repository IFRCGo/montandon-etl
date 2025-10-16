import json
from unittest.mock import MagicMock, patch

import pytest
from django.conf import settings
from django.core.serializers import serialize
from django.test import override_settings
from pystac_monty.sources.common import MontyDataTransformer

from apps.etl.etl_tasks.desinventar import ext_and_transform_desinventar_historical_data
from apps.etl.models import ExtractionData, PyStacLoadData, Transform
from apps.etl.tests.common.base_settings_test import TEST_CACHES
from apps.etl.utils import remove_ignored_keys
from main.configs import etl_config

MontyDataTransformer.base_collection_url = settings.BASE_DIR / "libs/pystac-monty/monty-stac-extension/examples"

TEST_CASES = [
    {
        "input": "desinventar.zip",
        "output": "output_desinventar.json",
        "expected": "fixed_output_desinventar.json",
        "country_code": "grd",
    },
]


@pytest.mark.django_db
@pytest.mark.parametrize("case", TEST_CASES)
@override_settings(TRANSFORM_SUCCESS_RATE=10, CELERY_TASK_ALWAYS_EAGER=True, CACHES=TEST_CACHES)
def test_handle_extraction_various_desinventar_files(case):
    input_filename = case["input"]
    expected_filename = case["expected"]
    country_code = case["country_code"]

    # Path to .zip file
    input_path = settings.BASE_DIR / "apps/etl/tests/dataset/desinventar" / input_filename
    with open(input_path, "rb") as f:
        zip_data = f.read()

    # Construct mock URL
    mock_url = f"{etl_config.DESINVENTAR_DATA_URL}/DesInventar/download/DI_export_{country_code}.zip"

    def custom_get(url, *args, **kwargs):
        if url == mock_url:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.content = zip_data
            mock_response.headers = {"Content-Type": "application/zip"}
        else:
            # Simulate failure for other countries
            mock_response = MagicMock()
            mock_response.status_code = 404
        return mock_response

    with patch("requests.get", side_effect=custom_get):
        ext_and_transform_desinventar_historical_data()

    # Assertions
    assert ExtractionData.objects.count() == 100
    assert Transform.objects.count() == 1
    assert PyStacLoadData.objects.count() == 372

    latest_data = PyStacLoadData.objects.all()
    latest_data_json = serialize("json", latest_data)
    actual_json = json.loads(latest_data_json)

    expected_path = settings.BASE_DIR / "apps/etl/tests/dataset/desinventar" / expected_filename
    assert expected_path.exists(), f"Expected reference file {expected_path} does not exist."
    with open(expected_path, "r", encoding="utf-8") as f:
        expected_json = json.load(f)

    ignored_keys = {"created_at", "modified_at", "monty:etl_id", "pk", "trace", "transform_id", "href"}

    filtered_actual = remove_ignored_keys(actual_json, ignored_keys)
    filtered_expected = remove_ignored_keys(expected_json, ignored_keys)

    assert filtered_actual == filtered_expected, f"Differences found when comparing to fixed file {expected_filename}."
