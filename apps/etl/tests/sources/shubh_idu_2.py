import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from django.conf import settings
from django.test import override_settings

from apps.etl.etl_tasks.idu import extract_and_transform_idu_data
from apps.etl.models import ExtractionData, Transform, PyStacLoadData

from pystac_monty.sources.common import MontyDataTransformer

MontyDataTransformer.base_collection_url = "/code/libs/pystac-monty/monty-stac-extension/examples"



@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
)
@pytest.mark.django_db
def test_handle_extraction_with_mocked_request():
    """
    Test the IDU extraction process by mocking the request sent to the extractor
    with the 'data' (source) payload, and ensuring Celery tasks run synchronously.
    """
    settings.CELERY_TASK_ALWAYS_EAGER = True  # Ensure tasks are run synchronously in tests

    json_file_path = Path('/code/apps/etl/Dataset/IDMC-IDU/idus.json')

    # Read mock data from the dynamically constructed path
    with open(json_file_path, 'r') as f:
        mock_data = json.load(f)

    url = "https://mock.url/endpoint"

    with patch('requests.get') as mock_get:
        # Mock response object with correct attributes
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_data  # Correct for .json() calls
        mock_response.content = json.dumps(mock_data).encode("utf-8")  # Correct for .content access
        mock_response.headers = {"Content-Type": "application/json"}

        mock_get.return_value = mock_response  # Assign mocked response to GET request

        # Call the static method directly on the class
        extract_and_transform_idu_data(url)

        assert (
            ExtractionData.objects.count(),
            Transform.objects.count(),
            PyStacLoadData.objects.count(),
        ) == (
            1,
            1,
            4340,
        )
        print(PyStacLoadData.objects.all())
        assert 1 == 2
