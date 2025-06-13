import json
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from django.conf import settings
from django.test import override_settings
from django.core.serializers import serialize

from apps.etl.etl_tasks.emdat import ext_and_transform_emdat_latest_data
from apps.etl.models import ExtractionData, Transform, PyStacLoadData

# Mocking the geocoding service
from pystac_monty.sources.common import MontyDataTransformer

MontyDataTransformer.base_collection_url = "/code/libs/pystac-monty/monty-stac-extension/examples"

# Country geometry mock data
mock_geocode_responses = {
    'AFG': {
        'country': 'Afghanistan',
        'geometry': {'type': 'Polygon', 'coordinates': [[[69.1, 34.5], [70.2, 34.6], [71.3, 34.8], [71.2, 34.3], [69.1, 34.5]]]},
        'bbox': [69.0, 34.0, 71.5, 35.0]
    },
    'AUS': {
        'country': 'Australia',
        'geometry': {'type': 'Polygon', 'coordinates': [[[144.0, -37.0], [145.0, -37.5], [146.0, -36.8], [144.5, -36.5], [144.0, -37.0]]]},
        'bbox': [144.0, -38.0, 146.0, -35.0]
    },
    'GNB': {
        'country': 'Guinea-Bissau',
        'geometry': {'type': 'Polygon', 'coordinates': [[[-15.0, 11.5], [-14.5, 12.0], [-14.0, 11.8], [-15.0, 11.5]]]},
        'bbox': [-15.5, 11.0, -13.5, 12.5]
    },
    'BOL': {
        'country': 'Bolivia',
        'geometry': {'type': 'Polygon', 'coordinates': [[[-68.1, -16.0], [-67.5, -16.5], [-67.0, -15.8], [-68.1, -16.0]]]},
        'bbox': [-69.0, -17.0, -66.5, -15.0]
    },
    'CHN': {
        'country': 'China',
        'geometry': {'type': 'Polygon', 'coordinates': [[[116.0, 39.9], [117.0, 39.7], [118.0, 40.0], [116.5, 40.3], [116.0, 39.9]]]},
        'bbox': [115.0, 39.0, 119.0, 41.0]
    },
    'PHL': {
        'country': 'Philippines',
        'geometry': {'type': 'Polygon', 'coordinates': [[[120.5, 14.6], [121.0, 14.7], [121.5, 14.8], [120.8, 14.5], [120.5, 14.6]]]},
        'bbox': [120.0, 14.0, 122.0, 15.0]
    },
    'NGA': {
        'country': 'Nigeria',
        'geometry': {'type': 'Polygon', 'coordinates': [[[8.0, 10.5], [9.0, 10.8], [9.5, 10.3], [8.5, 10.0], [8.0, 10.5]]]},
        'bbox': [7.5, 9.5, 10.0, 11.5]
    },
    'IND': {
        'country': 'India',
        'geometry': {'type': 'Polygon', 'coordinates': [[[77.0, 28.6], [77.5, 28.7], [78.0, 28.8], [77.5, 28.9], [77.0, 28.6]]]},
        'bbox': [76.5, 28.0, 78.5, 29.0]
    },
    'USA': {
        'country': 'United States',
        'geometry': {'type': 'Polygon', 'coordinates': [[[-77.0, 38.9], [-76.5, 39.0], [-76.0, 38.8], [-77.0, 38.7], [-77.0, 38.9]]]},
        'bbox': [-78.0, 38.5, -75.5, 39.5]
    },
    # Add more countries as needed
}

@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
@pytest.mark.django_db
@patch('requests.get')  # Patch requests.get to mock geocoder API
def test_handle_extraction_with_mocked_request(mock_get):
    """
    Test the EMDAT extraction process by mocking the request sent to the extractor.
    Ensures that Celery tasks run synchronously.
    """
    settings.CELERY_TASK_ALWAYS_EAGER = True

    def mock_get_side_effect(url, params=None, timeout=30):
        iso3 = params.get('iso3') if params else 'AFG'
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_geocode_responses.get(iso3, mock_geocode_responses['AFG'])
        return mock_response

    mock_get.side_effect = mock_get_side_effect

    json_file_path = Path('/code/apps/etl/Dataset/EM-DAT/EM-DAT.json')

    with open(json_file_path, 'r', encoding='utf-8') as f:
        mock_data = json.load(f)

    with patch('requests.post') as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_data
        mock_response.content = json.dumps(mock_data).encode("utf-8")
        mock_response.headers = {"Content-Type": "application/json"}
        mock_post.return_value = mock_response

        ext_and_transform_emdat_latest_data()

    assert ExtractionData.objects.count() == 1
    assert Transform.objects.count() == 1
    assert PyStacLoadData.objects.count() == 106

    latest_data = PyStacLoadData.objects.all().order_by('-id')[:10]
    latest_data_json = serialize('json', latest_data)

    output_path = Path('/code/output/output_emdat.json')
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as json_file:
        json_file.write(latest_data_json)

    assert output_path.exists(), f"Expected output JSON file {output_path} was not created."
