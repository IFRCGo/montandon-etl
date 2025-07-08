import json
import json5
from unittest.mock import patch

import pytest
from django.conf import settings
from django.core.serializers import serialize
from django.test import override_settings
from pystac_monty.sources.common import MontyDataTransformer

from apps.etl.etl_tasks.gfd import ext_and_transform_gfd_historical_data
from apps.etl.models import ExtractionData, PyStacLoadData, Transform
from apps.etl.utils import remove_ignored_keys

MontyDataTransformer.base_collection_url = (
    settings.BASE_DIR / "libs/pystac-monty/monty-stac-extension/examples"
)

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
    input_path = settings.BASE_DIR / "apps/etl/tests/dataset/gfd" / case["input"]
    with open(input_path, "r", encoding="utf-8") as f:
        mock_data = json5.load(f)

    with patch("apps.etl.extraction.sources.gfd.extract.GFDExtraction._get_flood_data", return_value=mock_data):
        ext_and_transform_gfd_historical_data()

    # Assertions
    assert ExtractionData.objects.count() == 1
    assert Transform.objects.count() == 1
    assert PyStacLoadData.objects.count() == 8  # Update if needed

    # Load expected output
    expected_path = settings.BASE_DIR / "apps/etl/tests/dataset/gfd" / case["expected"]
    assert expected_path.exists(), f"Expected file not found: {expected_path}"
    with open(expected_path, "r", encoding="utf-8") as f:
        expected_json = json.load(f)

    # Load actual DB output
    output_path = settings.BASE_DIR / "apps/etl/tests/dataset/gfd" / case["output"]
    actual_objects = PyStacLoadData.objects.all()
    actual_json_str = serialize("json", actual_objects)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(actual_json_str)
    actual_json = json.loads(actual_json_str)

    # # Compare filtered output
    # ignore_keys = {"created_at", "modified_at", "monty:etl_id", "pk"}
    # actual_clean = remove_ignored_keys(actual_json, ignore_keys)
    # expected_clean = remove_ignored_keys(expected_json, ignore_keys)
    # assert actual_clean == expected_clean, f"Mismatch with expected: {case['expected']}"
