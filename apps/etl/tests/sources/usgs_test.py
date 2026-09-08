import json
from unittest.mock import MagicMock, patch

import json5
import pytest
from django.conf import settings
from django.core.serializers import serialize
from django.test import override_settings
from pystac_monty.sources.common import MontyDataTransformer

from apps.etl.etl_tasks.usgs import ext_and_transform_usgs_latest_data
from apps.etl.models import ExtractionData, PyStacLoadData, Transform
from apps.etl.tests.common.base_settings_test import TEST_CACHES
from apps.etl.utils import remove_ignored_keys

# Set base_collection_url
MontyDataTransformer.base_collection_url = settings.BASE_DIR / "libs/pystac-monty/monty-stac-extension/examples"

# Define test cases
TEST_CASES = [
    {
        "input_files": {
            "query": "usgs_all_day.geojson",
            "detail": "usgs_detail.json",
            "losses": "losses.json",
            "alerts": "alerts.json",
        },
        "expected": "fixed_output_usgs.json",
    },
]


@pytest.mark.django_db
@pytest.mark.parametrize("case", TEST_CASES)
@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CACHES=TEST_CACHES)
def test_handle_extraction_various_usgs_files(case):
    dataset_dir = settings.BASE_DIR / "apps/etl/tests/dataset/usgs"

    # Load mock inputs
    with open(dataset_dir / case["input_files"]["query"], "r", encoding="utf-8") as f:
        query_data = json.load(f)
    with open(dataset_dir / case["input_files"]["detail"], "r", encoding="utf-8") as f:
        detail_data = json.load(f)
    with open(dataset_dir / case["input_files"]["losses"], "r", encoding="utf-8") as f:
        losses_data = json.load(f)
    with open(dataset_dir / case["input_files"]["alerts"], "r", encoding="utf-8") as f:
        alerts_data = json.load(f)

    # Setup mocks
    def mock_get(url, *args, **kwargs):
        if "fdsnws" in url:
            return _mock_response(query_data, content_type="application/geo+json")
        elif "detail" in url:
            return _mock_response(detail_data)
        elif "losses.json" in url:
            return _mock_response(losses_data)
        elif "alerts.json" in url:
            return _mock_response(alerts_data)
        return MagicMock(status_code=404)

    def _mock_response(data, content_type="application/json"):
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = data
        response.content = json.dumps(data).encode("utf-8")
        response.headers = {"Content-Type": content_type}
        return response

    # Patch requests
    with patch("requests.get", side_effect=mock_get):
        ext_and_transform_usgs_latest_data()

    # Assertions
    assert ExtractionData.objects.count() == 4
    assert Transform.objects.count() == 1
    assert PyStacLoadData.objects.count() == 4

    # Compare with expected output
    expected_path = dataset_dir / case["expected"]
    assert expected_path.exists(), f"Expected reference file {expected_path} does not exist."

    latest_data = PyStacLoadData.objects.all()
    actual_json = json.loads(serialize("json", latest_data))

    with open(expected_path, "r", encoding="utf-8") as f:
        expected_json = json5.load(f)

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
    actual_filtered = remove_ignored_keys(actual_json, ignored_keys)
    expected_filtered = remove_ignored_keys(expected_json, ignored_keys)

    assert actual_filtered == expected_filtered, f"Mismatch with expected file {case['expected']}"
