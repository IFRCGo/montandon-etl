import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from django.conf import settings
from django.test import override_settings
from django.core.serializers import serialize

from apps.etl.etl_tasks.emdat import ext_and_transform_emdat_latest_data
from apps.etl.models import ExtractionData, Transform, PyStacLoadData
from pystac_monty.sources.common import MontyDataTransformer

MontyDataTransformer.base_collection_url = "/code/libs/pystac-monty/monty-stac-extension/examples"

@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
@pytest.mark.django_db
def test_handle_extraction_with_mocked_request():
    """
    Test the GIDD extraction process by mocking the request sent to the extractor.
    Ensures that Celery tasks run synchronously.
    """
    settings.CELERY_TASK_ALWAYS_EAGER = True  # Ensure Celery tasks run synchronously in tests

    json_file_path = Path('/code/apps/etl/Dataset/EM-DAT/EM-DAT.json')

    # Read mock data from file
    with open(json_file_path, 'r') as f:
        mock_data = json.load(f)
        print("Mock Data:", mock_data)  # Check if data is correct

    # Patch 'requests.get' used inside 'ext_and_transform_emdat_latest_data'
    with patch('requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_data  # Mock .json() response

        # Ensure that content is also correctly mocked (return valid JSON as bytes)
        mock_response.content = json.dumps(mock_data).encode('utf-8')  # Mock .content
        mock_response.headers = {"Content-Type": "application/json"}

        # Mock requests.get() to return this response
        mock_get.return_value = mock_response

        # Call the function (without parameters) - it will use the patched requests.get
        ext_and_transform_emdat_latest_data()

    # Assertions: Check if data was correctly extracted and stored
    assert ExtractionData.objects.count() == 25
    assert Transform.objects.count() == 25
    assert PyStacLoadData.objects.count() == 400  # Ensure expected number of records

    # Fetch last processed data (latest 10 records)
    latest_data = PyStacLoadData.objects.all().order_by('-id')[:10]
    latest_data_json = serialize('json', latest_data)  # Convert queryset to JSON format
    latest_data_dict = json.loads(latest_data_json)  # Convert JSON string to dictionary

    # Save the latest processed data to a JSON file
    output_path = Path('/code/output/output_emdat.json')
    output_path.parent.mkdir(parents=True, exist_ok=True)  # Ensure the directory exists

    with open(output_path, 'w', encoding='utf-8') as json_file:
        json.dump(latest_data_dict, json_file, ensure_ascii=False, indent=4)

    # Assert JSON file was created
    assert output_path.exists(), f"Expected output JSON file {output_path} was not created."
