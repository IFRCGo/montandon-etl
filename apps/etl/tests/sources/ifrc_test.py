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
        "output": "output_ifrc.json",  # only used in logs now
        "expected": "fixed_output_ifrc.json",
    },
]


@pytest.mark.django_db
@pytest.mark.parametrize("case", TEST_CASES)
@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
def test_handle_extraction_various_ifrc_files(case):
    input_filename = case["input"]
    fixed_filename = case["expected"]

    # Load mock input
    input_path = settings.BASE_DIR / "apps/etl/tests/dataset/ifrc" / input_filename
    with open(input_path, "r", encoding="utf-8") as f:
        mock_data = json5.load(f)

    # IFRC data URL pattern
    def is_ifrc_url(url):
        return "appeal_type" in url and etl_config.IFRC_DATA_URL in url

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
        ext_and_transform_ifrcevent_latest_data()

    # DB assertions
    assert ExtractionData.objects.count() == 72
    assert Transform.objects.count() == 71
    assert PyStacLoadData.objects.count() == 70

    # Load expected output
    expected_output_path = settings.BASE_DIR / "apps/etl/tests/dataset/ifrc" / fixed_filename
    assert expected_output_path.exists(), f"Expected reference file {expected_output_path} does not exist."
    with open(expected_output_path, "r", encoding="utf-8") as expected_file:
        expected_json = json5.load(expected_file)

    # Load actual DB data
    latest_data = PyStacLoadData.objects.all()
    latest_data_json = serialize("json", latest_data)
    actual_json = json.loads(latest_data_json)

    # Keys to ignore in comparison
    ignored_keys = {"created_at", "modified_at", "monty:etl_id", "pk", "trace", "transform_id", "href"}

    filtered_actual = remove_ignored_keys(actual_json, ignored_keys)
    filtered_expected = remove_ignored_keys(expected_json, ignored_keys)

    assert filtered_actual == filtered_expected, f"Differences found when comparing to fixed file {fixed_filename}."
