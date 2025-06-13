import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from django.core.serializers import serialize
from django.test import override_settings
from django.conf import settings
from deepdiff import DeepDiff  # For comparing JSON

from apps.etl.etl_tasks.idu import ext_and_transform_idu_latest_data
from apps.etl.models import ExtractionData, Transform, PyStacLoadData
from pystac_monty.sources.common import MontyDataTransformer

# Set base_collection_url
MontyDataTransformer.base_collection_url = settings.BASE_DIR / "libs/pystac-monty/monty-stac-extension/examples"

# Define your test cases
TEST_CASES = [
    ("idus.json", "output_idu.json", "fixed_output_idu.json"),
    ("mismatch_idu.json", "output_mismatch_idu.json", "fixed_output_mismatch_idu.json"),
    ("missing_idu.json", "output_missing_idu.json", "fixed_output_missing_idu.json"),
    ("unordered_idu.json", "output_unordered_idu.json", "fixed_output_unordered_idu.json"),
    ("unstructured_idu.json", "output_unstructured_idu.json", "fixed_output_unstructured_idu.json"),
]

@pytest.mark.django_db
@pytest.mark.parametrize("input_filename, output_filename, fixed_filename", TEST_CASES)
@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
def test_handle_extraction_various_idu_files(input_filename, output_filename, fixed_filename):
    # Path to input JSON file
    input_path = settings.BASE_DIR / 'apps/etl/Dataset/IDMC-IDU' / input_filename

    # Load mock JSON data
    with open(input_path, 'r', encoding='utf-8') as f:
        mock_data = json.load(f)

    # Patch requests.get to return mock data
    with patch('requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_data
        mock_response.content = json.dumps(mock_data).encode("utf-8")
        mock_response.headers = {"Content-Type": "application/json"}
        mock_get.return_value = mock_response

        # Run ETL task
        ext_and_transform_idu_latest_data()

    # Define output directory
    output_dir = settings.BASE_DIR / "output/IDU_Output/"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / output_filename

    # Serialize PyStacLoadData queryset to JSON
    latest_data = PyStacLoadData.objects.all()
    latest_data_json = serialize('json', latest_data)

    # Write output JSON
    with open(output_path, 'w', encoding='utf-8') as json_file:
        json_file.write(latest_data_json)

    # Assertions for object creation
    assert output_path.exists(), f"Expected output file {output_path} was not created."
    assert ExtractionData.objects.count() == 1
    assert Transform.objects.count() == 1
    assert PyStacLoadData.objects.count() > 0

    # Load actual and expected JSON
    expected_output_path = settings.BASE_DIR / "output/IDU_Output" / fixed_filename
    assert expected_output_path.exists(), f"Expected reference file {expected_output_path} does not exist."

    with open(output_path, 'r', encoding='utf-8') as actual_file:
        actual_json = json.load(actual_file)

    with open(expected_output_path, 'r', encoding='utf-8') as expected_file:
        expected_json = json.load(expected_file)

    # Fields to ignore during comparison
    ignored_fields = {
        "fields.created_at",
        "fields.modified_at",
        "fields.item.properties.monty:etl_id",
    }

    # Compare JSON content using DeepDiff with ignored fields
    diff = DeepDiff(
        expected_json,
        actual_json,
        ignore_order=True,
        exclude_paths=ignored_fields,
    )

    # Print specific paths of differences if found
    if diff:
        print(f"\n❌ Differences found in {fixed_filename}:\n")
        for category, changes in diff.items():
            print(f"--- {category} ---")
            for change in changes:
                print(f"{change}")
        assert False, f"Differences found when comparing to fixed file {fixed_filename} (see printed output above)."
