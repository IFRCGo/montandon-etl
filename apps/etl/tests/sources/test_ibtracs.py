import pytest
import pandas as pd
from pathlib import Path
from unittest.mock import patch, MagicMock
from django.conf import settings
from django.test import override_settings
from django.core.serializers import serialize

from apps.etl.etl_tasks.noaa_IBTrACS import ext_and_transform_ibtracs_latest_data
from apps.etl.models import ExtractionData, Transform, PyStacLoadData

from pystac_monty.sources.common import MontyDataTransformer

MontyDataTransformer.base_collection_url = "/code/libs/pystac-monty/monty-stac-extension/examples"

@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
@pytest.mark.django_db
def test_handle_extraction_with_mocked_request():
    """
    Test the IBtracs extraction process by mocking the request to return CSV data.
    Ensures that Celery tasks run synchronously.
    """
    settings.CELERY_TASK_ALWAYS_EAGER = True

    csv_file_path = Path('/code/apps/etl/Dataset/Ibtracs/ibtracs.ACTIVE.list.v04r01.csv')

    # Read the CSV file content
    with open(csv_file_path, 'r', encoding='utf-8') as f:
        mock_csv_data = f.read()

    def _get(url, *args, **kwargs):
        print(url)
        if url == 'http://192.168.87.13:8501/country/iso3':
            return {}
        return mock_response

    # Patch 'requests.get' used inside 'ext_and_transform_ibtracs_latest_data'
    with patch('requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = mock_csv_data.encode("utf-8")
        mock_response.text = mock_csv_data
        mock_response.headers = {"Content-Type": "text/csv"}
        mock_get.side_effect = _get

        # Call the ETL function (uses patched requests.get)
        ext_and_transform_ibtracs_latest_data()

    # Assertions
    assert ExtractionData.objects.count() == 1
    assert Transform.objects.count() == 1
    assert PyStacLoadData.objects.count() == 116 # Adjust based on your expected output

    # Serialize recent data to JSON
    latest_data = PyStacLoadData.objects.all().order_by('-id')[:10]
    latest_data_json = serialize('json', latest_data)

    # Write to output file
    output_path = Path('/code/output/output_ibtracs.json')
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as json_file:
        json_file.write(latest_data_json)

    assert output_path.exists(), f"Expected output JSON file {output_path} was not created."
