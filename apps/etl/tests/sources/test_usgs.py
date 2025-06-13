import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from django.conf import settings
from django.test import override_settings
from django.core.serializers import serialize
import requests  # <-- needed for real_requests_get

from apps.etl.etl_tasks.usgs import ext_and_transform_usgs_latest_data
from apps.etl.models import ExtractionData, Transform, PyStacLoadData

from pystac_monty.sources.common import MontyDataTransformer

MontyDataTransformer.base_collection_url = "/code/libs/pystac-monty/monty-stac-extension/examples"

@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
@pytest.mark.django_db
def test_handle_extraction_with_mocked_request():
    """
    Test the USGS extraction process by mocking only the data sources,
    and allowing real geocoder to be called at http://localhost:8002
    """
    settings.CELERY_TASK_ALWAYS_EAGER = True

    # Load mock QUERY response (event list)
    query_response = json.load(open("/code/apps/etl/Dataset/USGS/USGS_all_day.geojson"))

    # Load mock DETAIL response (includes losspager)
    detail_response = json.load(open("/code/apps/etl/Dataset/USGS/mock_detail.geojson"))

    # Load mock LOSSES response
    losses_response = json.load(open("/code/apps/etl/Dataset/USGS/mock_losses.json"))

    # Use real requests.get for non-mocked URLs
    real_requests_get = requests.get

    with patch('requests.get') as mock_get:
        def mock_get_side_effect(url, *args, **kwargs):
            if "all_day" in url:
                return _mock_response(query_response, content_type="application/geo+json")
            elif "detail" in url:
                return _mock_response(detail_response)
            elif "losses.json" in url:
                return _mock_response(losses_response)
            else:
                # Let other requests like geocoder pass through
                return real_requests_get(url, *args, **kwargs)

        mock_get.side_effect = mock_get_side_effect

        # Run the ETL function
        ext_and_transform_usgs_latest_data()

    # Assertions
    assert ExtractionData.objects.count() == 465
    assert Transform.objects.count() == 232
    assert PyStacLoadData.objects.count() == 696

    # Fetch latest data
    latest_data = PyStacLoadData.objects.all().order_by('-id')[:10]
    latest_data_json = serialize('json', latest_data)

    # Save serialized JSON to a file
    output_path = Path('/code/output/output_usgs.json')
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as json_file:
        json_file.write(latest_data_json)

    # Final assertion
    assert output_path.exists(), f"Expected output JSON file {output_path} was not created."


def _mock_response(json_data, content_type="application/json"):
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = json_data
    response.content = json.dumps(json_data).encode("utf-8")
    response.headers = {"Content-Type": content_type}
    return response
