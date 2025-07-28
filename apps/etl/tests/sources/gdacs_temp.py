import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from django.core.serializers import serialize
from django.test import override_settings
from pystac_monty.sources.common import MontyDataTransformer

from apps.etl.etl_tasks.gdacs import ext_and_transform_gdacs_latest_data
from apps.etl.models import ExtractionData, PyStacLoadData, Transform
from main.configs import etl_config

MontyDataTransformer.base_collection_url = "/code/libs/pystac-monty/monty-stac-extension/examples"

# Exact URLs for mocking
step1_eventlist_url = f"{etl_config.GDACS_URL}/gdacsapi/api/events/geteventlist/SEARCH"
step2_detail_url = "https://www.gdacs.org/gdacsapi/api/events/geteventdata?eventid=1466272&eventtype=EQ"
step3_episode_url = "https://www.gdacs.org/gdacsapi/api/events/getepisodedata?eventtype=EQ&eventid=1466272&episodeid=1620062"
step4_geom_url = "https://www.gdacs.org/gdacsapi/api/polygons/getgeometry?eventtype=EQ&eventid=1466272&episodeid=1620062"


@pytest.mark.django_db
def test_handle_gdacs_extraction_with_mocked_request():
    """
    Test the GDACS extraction process using mocked event and geometry data.
    Ensures that no live GDACS API calls are made.
    """
    test_date = (datetime.now() - timedelta(days=30)).date()

    with override_settings(CELERY_TASK_ALWAYS_EAGER=True, GDACS_START_DATE=test_date):
        # Load mock data from local files
        eventlistdata = json.load(open("apps/etl/tests/dataset/gdacs/start_eventlist.json"))
        event_detail_data = json.load(open("apps/etl/tests/dataset/gdacs/step2_detail.json"))
        episode_1_data = json.load(open("apps/etl/tests/dataset/gdacs/step3_first_episode.json"))
        episode_1_geom_data = json.load(open("apps/etl/tests/dataset/gdacs/step4_first_episodes_geometry.json"))

        # Patch the CachedSession.get method from gdacs.py
        with patch("apps.etl.etl_tasks.gdacs.session.get") as mock_get:

            def mock_get_side_effect(url, *args, **kwargs):
                base_url = url.split("?", 1)[0]

                if base_url == step1_eventlist_url:
                    return _mock_response(eventlistdata)
                elif url == step2_detail_url:
                    return _mock_response(event_detail_data)
                elif url == step3_episode_url:
                    return _mock_response(episode_1_data)
                elif url == step4_geom_url:
                    return _mock_response(episode_1_geom_data)
                else:
                    raise RuntimeError(f"Unexpected URL called in test: {url}")

            mock_get.side_effect = mock_get_side_effect

            # Run the ETL pipeline
            ext_and_transform_gdacs_latest_data()

        # Assertions
        assert ExtractionData.objects.count() == 46
        assert Transform.objects.count() == 11
        assert PyStacLoadData.objects.count() == 22

        # Save last 10 transformed records
        latest_data = PyStacLoadData.objects.order_by("-id")[:10]
        latest_data_json = serialize("json", latest_data)

        output_path = Path("/code/output/output_gdacs.json")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(latest_data_json)

        assert output_path.exists(), "Expected output file was not created."


def _mock_response(json_data, content_type="application/json"):
    """Helper to create a mock HTTP response object."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = json_data
    mock_resp.content = json.dumps(json_data).encode("utf-8")
    mock_resp.headers = {"Content-Type": content_type}
    return mock_resp
