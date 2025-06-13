import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from django.conf import settings
from django.test import override_settings
from django.core.serializers import serialize
import requests

from apps.etl.etl_tasks.gdacs import ext_and_transform_gdacs_latest_data  # Adjust if different
from apps.etl.models import ExtractionData, Transform, PyStacLoadData

from pystac_monty.sources.common import MontyDataTransformer

MontyDataTransformer.base_collection_url = "/code/libs/pystac-monty/monty-stac-extension/examples"

@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
@pytest.mark.django_db
def test_handle_gdacs_extraction_with_mocked_request():
    """
    Test the GDACS extraction process using mocked event and geometry data for Spain Flood.
    """
    settings.CELERY_TASK_ALWAYS_EAGER = True

    # Load mock data from local files
    main_event_data = json.load(open("/code/apps/etl/Dataset/GDACS/1102983-1-geteventdata-source.json"))
    episode1_event = json.load(open("/code/apps/etl/Dataset/GDACS/1102983-1-event.json"))
    episode1_geometry = json.load(open("/code/apps/etl/Dataset/GDACS/1102983-1-geometry.json"))
    episode2_event = json.load(open("/code/apps/etl/Dataset/GDACS/1102983-2-event.json"))
    episode2_geometry = json.load(open("/code/apps/etl/Dataset/GDACS/1102983-2-geometry.json"))

    # Use real requests.get for non-mocked URLs
    real_requests_get = requests.get

    with patch("requests.get") as mock_get:
        def mock_get_side_effect(url, *args, **kwargs):
            if "1102983-1-geteventdata-source.json" in url:
                return _mock_response(main_event_data)
            elif "getepisodedata?eventtype=FL&eventid=1102983&episodeid=1" in url:
                return _mock_response(episode1_event)
            elif "getgeometry?eventtype=FL&eventid=1102983&episodeid=1" in url:
                return _mock_response(episode1_geometry)
            elif "getepisodedata?eventtype=FL&eventid=1102983&episodeid=2" in url:
                return _mock_response(episode2_event)
            elif "getgeometry?eventtype=FL&eventid=1102983&episodeid=2" in url:
                return _mock_response(episode2_geometry)
            else:
                return real_requests_get(url, *args, **kwargs)

        mock_get.side_effect = mock_get_side_effect

        # Run the ETL pipeline
        ext_and_transform_gdacs_latest_data()

    # Basic model assertions
    assert ExtractionData.objects.exists()
    assert Transform.objects.exists()
    assert PyStacLoadData.objects.exists()

    # Save last 10 transformed records to output file
    latest_data = PyStacLoadData.objects.order_by("-id")[:10]
    latest_data_json = serialize("json", latest_data)

    output_path = Path("/code/output/output_gdacs.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(latest_data_json)

    assert output_path.exists(), "Expected output file was not created."


def _mock_response(json_data, content_type="application/json"):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = json_data
    mock_resp.content = json.dumps(json_data).encode("utf-8")
    mock_resp.headers = {"Content-Type": content_type}
    return mock_resp
