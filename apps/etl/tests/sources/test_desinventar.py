# apps/etl/tests/sources/test_desinventar.py
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from django.conf import settings
from django.test import override_settings
from django.core.serializers import serialize

# Import the models used in assertions
from apps.etl.models import ExtractionData, Transform, PyStacLoadData

@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
@pytest.mark.django_db
def test_handle_extraction_with_mocked_request():
    """
    Test the GIDD extraction process by mocking the request sent to the extractor.
    Ensures that Celery tasks run synchronously.
    """
    settings.CELERY_TASK_ALWAYS_EAGER = True

    # Path to XML file
    json_file_path = Path('/code/apps/etl/Dataset/Desinventar/DI_export_npl.xml')

    # Read mock data from XML file
    with open(json_file_path, 'r', encoding='utf-8') as f:
        xml_data = f.read()

    # Parse XML
    import xml.etree.ElementTree as ET
    root = ET.fromstring(xml_data)

    # Convert XML data to a structure that can be used (optional - not used later)
    mock_data = []
    for item in root.findall('.//data_item'):  # Adjust XPath as needed
        data_dict = {
            'field1': item.find('field1').text if item.find('field1') is not None else None,
            'field2': item.find('field2').text if item.find('field2') is not None else None,
        }
        mock_data.append(data_dict)

    # Patch 'requests.get'
    with patch('requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = xml_data.encode("utf-8")
        mock_response.headers = {"Content-Type": "application/xml"}
        mock_get.return_value = mock_response

        # Import inside the test function to avoid circular import
        from apps.etl.etl_tasks.desinventar import ext_and_transform_desinventar_data

        # Call the ETL function
        ext_and_transform_desinventar_data()

    # Assertions
    assert ExtractionData.objects.count() == 1
    assert Transform.objects.count() == 1
    assert PyStacLoadData.objects.count() == 3592

    # Fetch latest data
    latest_data = PyStacLoadData.objects.all().order_by('-id')[:10]
    latest_data_json = serialize('json', latest_data)

    # Save JSON string directly to file
    output_path = Path('/code/output/output_desinventar.json')
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as json_file:
        json_file.write(latest_data_json)

    # Final assertion
    assert output_path.exists(), f"Expected output JSON file {output_path} was not created."
