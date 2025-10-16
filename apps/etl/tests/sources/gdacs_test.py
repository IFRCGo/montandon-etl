import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
import requests
from django.test import override_settings
from pystac_monty.sources.common import MontyDataTransformer

from apps.etl.etl_tasks.gdacs import ext_and_transform_gdacs_historical_data
from apps.etl.etl_tasks.segment_gdacs import deep_dive
from apps.etl.models import ExtractionData, PyStacLoadData, Transform
from apps.etl.tests.common.base_settings_test import TEST_CACHES
from apps.etl.utils import remove_ignored_keys

MontyDataTransformer.base_collection_url = "/code/libs/pystac-monty/monty-stac-extension/examples"

TEST_DATE = "2025-02-05"

step2_detail_url = "https://www.gdacs.org/gdacsapi/api/events/geteventdata?eventid=1466272&eventtype=EQ"
step3_episode_url = "https://www.gdacs.org/gdacsapi/api/events/getepisodedata?eventtype=EQ&eventid=1466272&episodeid=1620062"
step4_geom_url = "https://www.gdacs.org/gdacsapi/api/polygons/getgeometry?eventtype=EQ&eventid=1466272&episodeid=1620062"


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CACHES=TEST_CACHES)
@pytest.mark.django_db
def test_handle_gdacs_extraction_with_mocked_request():
    """
    Test the GDACS extraction process.
    Force extractor to only run for 2025-02-05.
    """

    # Load mock data from local files
    eventlistdata = json.load(open("apps/etl/tests/dataset/gdacs/start_eventlist.json"))
    event_detail_data = json.load(open("apps/etl/tests/dataset/gdacs/step2_detail.json"))
    episode_1_data = json.load(open("apps/etl/tests/dataset/gdacs/step3_first_episode.json"))
    episode_1_geom_data = json.load(open("apps/etl/tests/dataset/gdacs/step4_first_episodes_geometry.json"))

    # Load fixed output reference
    expected_output = json.load(open("apps/etl/tests/dataset/gdacs/fixed_output_gdacs.json"))

    # Use real requests.get for non-mocked URLs
    real_requests_get = requests.get

    def mock_get_side_effect(url, *args, **kwargs):
        if "geteventlist" in url:
            return _mock_response(eventlistdata)
        elif url == step2_detail_url:
            return _mock_response(event_detail_data)
        elif url == step3_episode_url:
            return _mock_response(episode_1_data)
        elif url == step4_geom_url:
            return _mock_response(episode_1_geom_data)
        else:
            return real_requests_get(url, *args, **kwargs)

    with patch("requests.get") as mock_get, patch("apps.etl.etl_tasks.segment_gdacs.deep_dive") as mock_deep_dive:
        # Force deep_dive to always use TEST_DATE
        def deep_dive_side_effect(session, hazard, start_date, end_date, size, extra):
            forced_start = forced_end = datetime.strptime(TEST_DATE, "%Y-%m-%d").date()
            return deep_dive(session, hazard, forced_start, forced_end, size, extra)

        mock_deep_dive.side_effect = deep_dive_side_effect
        mock_get.side_effect = mock_get_side_effect

        # Run the ETL pipeline
        ext_and_transform_gdacs_historical_data()

    # Basic model assertions
    assert ExtractionData.objects.count() == 12
    assert Transform.objects.count() == 1
    assert PyStacLoadData.objects.count() == 2

    # Compare actual output with fixed JSON (ignoring volatile fields)
    latest_data = list(PyStacLoadData.objects.values())
    ignore_keys = ["created_at", "modified_at", "monty:etl_id", "pk", "trace_id", "transform_id_id", "item_datetime", "id"]

    filtered_actual = remove_ignored_keys(latest_data, ignore_keys)
    filtered_expected = remove_ignored_keys(expected_output, ignore_keys)

    assert filtered_actual == filtered_expected, "GDACS output does not match fixed_output_gdacs.json"


def _mock_response(json_data, content_type="application/json"):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = json_data
    mock_resp.content = json.dumps(json_data).encode("utf-8")
    mock_resp.headers = {"Content-Type": content_type}
    return mock_resp
