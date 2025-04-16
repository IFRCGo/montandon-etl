#ERROR RUnning but the data not stored or idk what is happening
import pytest
from unittest.mock import patch, MagicMock
from django.conf import settings
from django.test import override_settings
from django.core.serializers import serialize
import csv
import json
from pathlib import Path

from apps.etl.etl_tasks.noaa_IBTrACS import ext_and_transform_ibtracs_latest_data
from apps.etl.models import ExtractionData, Transform, PyStacLoadData

from pystac_monty.sources.common import MontyDataTransformer

MontyDataTransformer.base_collection_url = "/code/libs/pystac-monty/monty-stac-extension/examples"

@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
@pytest.mark.django_db
def test_handle_extraction_with_mocked_request():
    """
    Test the IBTRACS extraction process by mocking the request sent to the extractor.
    Ensures that Celery tasks run synchronously.
    """
    settings.CELERY_TASK_ALWAYS_EAGER = True

    csv_file_path = Path('/code/apps/etl/Dataset/Ibtracs/ibrtacs.csv')

    # Read CSV data into a list of dictionaries
    with open(csv_file_path, 'r', encoding='utf-8') as f:
        csv_reader = csv.DictReader(f)
        csv_data = [row for row in csv_reader]

    # Patch 'requests.get' used inside 'ext_and_transform_ibtracs_latest_data'
    with patch('requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200

        # Convert CSV data into a JSON-like structure for the mock response
        mock_response.json.return_value = csv_data
        mock_response.content = json.dumps(csv_data).encode("utf-8")
        mock_response.headers = {"Content-Type": "text/csv"}
        mock_get.return_value = mock_response

        # Call the ETL function (uses patched requests.get)
        ext_and_transform_ibtracs_latest_data()

    # Assertions
    assert ExtractionData.objects.count() == 1
    assert Transform.objects.count() == 1
    assert PyStacLoadData.objects.count() == 0

    # Fetch the latest data
    latest_data = PyStacLoadData.objects.all().order_by('-id')[:10]
    latest_data_json = serialize('json', latest_data)

    # Save the JSON string to a file
    output_path = Path('/code/output/output_ibtracs.json')
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as json_file:
        json_file.write(latest_data_json)

    # Final assertion
    assert output_path.exists(), f"Expected output JSON file {output_path} was not created."
