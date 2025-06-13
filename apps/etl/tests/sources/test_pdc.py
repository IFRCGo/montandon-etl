from shapely.geometry import geo
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from django.conf import settings
from django.test import override_settings
from django.core.serializers import serialize

from apps.etl.etl_tasks.pdc import extract_and_transform_pdc_data
from apps.etl.models import ExtractionData, Transform, PyStacLoadData

from pystac_monty.sources.common import MontyDataTransformer

MontyDataTransformer.base_collection_url = "/code/libs/pystac-monty/monty-stac-extension/examples"

@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
@pytest.mark.django_db
def test_handle_extraction_with_mocked_request():
    """
    Test the PDC extraction process by mocking all requests used during extraction.
    Ensures Celery tasks run synchronously in tests.
    """
    base_path = Path("apps/etl/Dataset/PDC/")

    hazard_file = base_path / "hazard_data.json"
    geo_file = base_path / "hazard_geo.geojson"
    exposure_list = base_path / "exposure_list.json"
    exposure_file = base_path / "exposure_detail.json"

    with open(hazard_file, "r") as f:
        hazard_data = json.load(f)

    with open(geo_file, "r") as f:
        geo_json_content = f.read()
        geo_data = json.loads(geo_json_content), "fake-url"

    with open(exposure_file, "r") as f:
        exposure_detail = json.load(f)

    with open(exposure_list, "r") as f:
        exposure_list = json.load(f)

    # Create mock responses
    mock_hazard_response = MagicMock()
    mock_hazard_response.status_code = 200
    mock_hazard_response.json.return_value = hazard_data
    mock_hazard_response.headers = {'content-type': 'application/json'}
    mock_hazard_response.content = json.dumps(hazard_data).encode('utf-8')

    mock_exposure_ids_response = MagicMock()
    mock_exposure_ids_response.status_code = 200
    mock_exposure_ids_response.json.return_value = exposure_list
    mock_exposure_ids_response.headers = {'content-type': 'application/json'}
    mock_exposure_ids_response.content = json.dumps(exposure_list).encode('utf-8')

    mock_exposure_geo_response = MagicMock()
    mock_exposure_geo_response.status_code = 200
    mock_exposure_geo_response.json.return_value = geo_data
    mock_exposure_geo_response.headers = {'content-type': 'application/json'}
    mock_exposure_geo_response.content = json.dumps(geo_data).encode('utf-8')



    mock_exposure_detail_response = MagicMock()
    mock_exposure_detail_response.status_code = 200
    mock_exposure_detail_response.json.return_value = exposure_detail
    mock_exposure_detail_response.headers = {'content-type': 'application/json'}
    mock_exposure_detail_response.content = json.dumps(exposure_detail).encode('utf-8')

    # Correct patch paths: adjust if requests.get is used in another module
    with patch('requests.post') as mock_get, \
         patch('apps.etl.utils.AccessTokenManager.get_polygon', return_value=geo_data), \
         patch('apps.etl.utils.AccessTokenManager.get_access_token', return_value="fake-token"):

        mock_get.side_effect = [
            mock_hazard_response,
            mock_exposure_ids_response,
            mock_exposure_detail_response,
            mock_exposure_geo_response
        ]
        # Call the ETL function (uses patched requests.get)
        extract_and_transform_pdc_data()

    # Assertions
    assert ExtractionData.objects.count() == 17
    assert Transform.objects.count() == 0
    assert PyStacLoadData.objects.count() == 0

    # Fetch latest data
    latest_data = PyStacLoadData.objects.all().order_by('-id')[:10]
    latest_data_json = serialize('json', latest_data)


    # Save JSON string directly to file
    output_path = Path('/code/output/output_pdc.json')
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as json_file:
        json_file.write(latest_data_json)

    # Final assertion
    assert output_path.exists(), f"Expected output JSON file {output_path} was not created."
