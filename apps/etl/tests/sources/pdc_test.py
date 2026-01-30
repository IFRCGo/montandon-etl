import json
from unittest.mock import MagicMock, patch

import pytest
from django.conf import settings
from django.core.serializers import serialize
from django.test import override_settings
from pystac_monty.sources.common import MontyDataTransformer

from apps.etl.etl_tasks.pdc import extract_and_transform_pdc_latest_data
from apps.etl.models import ExtractionData, PyStacLoadData, Transform
from apps.etl.tests.common.base_settings_test import TEST_CACHES
from apps.etl.utils import remove_ignored_keys

# Set base_collection_url
MontyDataTransformer.base_collection_url = settings.BASE_DIR / "libs/pystac-monty/monty-stac-extension/examples"

# Define test case(s)
TEST_CASES = [
    {
        "input_files": {
            "hazard": "hazard_data.json",
            "geo": "hazard_geo.geojson",
            "exposure_list": "exposure_list.json",
            "exposure_detail": "exposure_detail.json",
        },
        "expected": "fixed_output_pdc.json",
    },
]


@pytest.mark.django_db
@pytest.mark.parametrize("case", TEST_CASES)
@override_settings(TRANSFORM_SUCCESS_RATE=20, CELERY_TASK_ALWAYS_EAGER=True, CACHES=TEST_CACHES)
def test_handle_extraction_various_pdc_files(case):
    dataset_dir = settings.BASE_DIR / "apps/etl/tests/dataset/pdc"

    # Load mock inputs
    with open(dataset_dir / case["input_files"]["hazard"], "r", encoding="utf-8") as f:
        hazard_data = json.load(f)
    with open(dataset_dir / case["input_files"]["geo"], "r", encoding="utf-8") as f:
        geo_data = json.load(f)
    with open(dataset_dir / case["input_files"]["exposure_list"], "r", encoding="utf-8") as f:
        exposure_list = json.load(f)
    with open(dataset_dir / case["input_files"]["exposure_detail"], "r", encoding="utf-8") as f:
        exposure_detail = json.load(f)

    # Setup mocks
    def mock_post(url, *args, **kwargs):
        if "search_hazard" in url:
            return _mock_response(hazard_data)
        return MagicMock(status_code=404)

    def mock_get(url, *args, **kwargs):
        if "exposure/1751032040.9863468" in url:
            return _mock_response(exposure_detail)
        elif "hazard/62006159-a6da-45d8-b739-8d0940876fa1/exposure" in url:
            return _mock_response(exposure_list)
        elif "get_mags?hazard_id=352320" in url:
            return _mock_response(geo_data)
        return MagicMock(status_code=404)

    def _mock_response(data):
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = data
        response.content = json.dumps(data).encode("utf-8")
        response.headers = {"Content-Type": "application/json"}
        return response

    # Patch requests
    with patch("requests.get", side_effect=mock_get), patch("requests.post", side_effect=mock_post):
        extract_and_transform_pdc_latest_data()

    # Assertions
    assert ExtractionData.objects.count() == 60
    assert Transform.objects.count() == 15
    assert PyStacLoadData.objects.count() == 315

    # Compare with expected output
    expected_path = dataset_dir / case["expected"]
    assert expected_path.exists(), f"Expected reference file {expected_path} does not exist."

    latest_data = PyStacLoadData.objects.all().order_by("-id")[:10]
    actual_json = json.loads(serialize("json", latest_data))

    with open(expected_path, "r", encoding="utf-8") as f:
        expected_json = json.load(f)

    ignored_keys = {
        "stac_extensions",
        "created_at",
        "modified_at",
        "monty:corr_id",
        "monty:guid",
        "monty:etl_id",
        "pk",
        "trace",
        "transform_id",
        "href",
        "keywords",
    }
    actual_filtered = remove_ignored_keys(actual_json, ignored_keys)
    expected_filtered = remove_ignored_keys(expected_json, ignored_keys)

    assert actual_filtered == expected_filtered, f"Mismatch with expected file {case['expected']}"
