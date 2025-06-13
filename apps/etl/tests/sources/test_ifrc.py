# rebase your branch to  project/historical-gdacs-pdc
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from django.conf import settings
from django.test import override_settings
from django.core.serializers import serialize

from apps.etl.etl_tasks.ifrc_event import ext_and_transform_ifrcevent_latest_data
from apps.etl.models import ExtractionData, Transform, PyStacLoadData

from pystac_monty.sources.common import MontyDataTransformer

MontyDataTransformer.base_collection_url = "/code/libs/pystac-monty/monty-stac-extension/examples"

@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
@pytest.mark.django_db
def test_handle_extraction_with_mocked_request():
    """
    Test the IFRC extraction process by mocking the request sent to the extractor.
    Ensures that Celery tasks run synchronously.
    """
    settings.CELERY_TASK_ALWAYS_EAGER = True

    json_file_path = Path('/code/apps/etl/Dataset/IFRC/IFRC.json')

    # Read mock data from file
    with open(json_file_path, 'r', encoding='utf-8') as f:
        mock_data = json.load(f)

    # Patch 'requests.get' used inside 'ext_and_transform_gidd_latest_data'
    with patch('requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_data
        mock_response.content = json.dumps(mock_data).encode("utf-8")
        mock_response.headers = {"Content-Type": "application/json"}
        mock_get.return_value = mock_response

        # Call the ETL function (uses patched requests.get)
        ext_and_transform_ifrcevent_latest_data()

    # Assertions
    assert ExtractionData.objects.count() == 1
    assert Transform.objects.count() == 1
    assert PyStacLoadData.objects.count() == 0

    # Fetch latest data
    latest_data = PyStacLoadData.objects.all().order_by('-id')[:10]
    latest_data_json = serialize('json', latest_data)

    # Save JSON string directly to file
    output_path = Path('/code/output/output_ifrc.json')
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as json_file:
        json_file.write(latest_data_json)

    # Final assertion
    assert output_path.exists(), f"Expected output JSON file {output_path} was not created."
