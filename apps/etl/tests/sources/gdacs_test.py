import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from django.core.serializers import serialize
from django.test import override_settings
from pystac_monty.sources.common import MontyDataTransformer

from apps.etl.etl_tasks.gdacs import ext_and_transform_gdacs_latest_data
from apps.etl.etl_tasks.segment_gdacs import deep_dive
from apps.etl.models import ExtractionData, PyStacLoadData, Transform
from apps.etl.tests.common.base_settings_test import TEST_CACHES
from apps.etl.utils import remove_ignored_keys

MontyDataTransformer.base_collection_url = "/code/libs/pystac-monty/monty-stac-extension/examples"

TEST_DATE = "2025-02-05"
DATASET_DIR = "apps/etl/tests/dataset/gdacs"

HAZARD_TEST_PARAMS = [
    pytest.param(
        "EQ",
        "https://www.gdacs.org/gdacsapi/api/events/getepisodedata?eventtype=EQ&eventid=1466272&episodeid=1620062",
        "https://www.gdacs.org/gdacsapi/api/polygons/getgeometry?eventtype=EQ&eventid=1466272&episodeid=1620062",
        2,
        "fixed_output_gdacs_eq.json",
        id="EQ",
    ),
    pytest.param(
        "FL",
        "https://www.gdacs.org/gdacsapi/api/events/getepisodedata?eventtype=FL&eventid=1103107&episodeid=16",
        "https://www.gdacs.org/gdacsapi/api/polygons/getgeometry?eventtype=FL&eventid=1103107&episodeid=16",
        2,
        "fixed_output_gdacs_fl.json",
        id="FL",
    ),
]


def _mock_response(json_data, content_type="application/json"):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = json_data
    mock_resp.content = json.dumps(json_data).encode("utf-8")
    mock_resp.headers = {"Content-Type": content_type}
    return mock_resp


@pytest.mark.parametrize("hazard,step3_url,step4_url,expected_pystac_count,fixed_output_file", HAZARD_TEST_PARAMS)
@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CACHES=TEST_CACHES)
@pytest.mark.django_db
def test_handle_gdacs_extraction_with_mocked_request(hazard, step3_url, step4_url, expected_pystac_count, fixed_output_file):
    """
    Test the GDACS extraction process for a given hazard type.
    Force extractor to only run for 2025-02-05.
    """
    hazard_lower = hazard.lower()

    eventlistdata = json.load(open(f"{DATASET_DIR}/start_eventlist_{hazard_lower}.json"))
    event_detail_data = json.load(open(f"{DATASET_DIR}/step2_detail_{hazard_lower}.json"))
    episode_1_data = json.load(open(f"{DATASET_DIR}/step3_first_episode_{hazard_lower}.json"))
    episode_1_geom_data = json.load(open(f"{DATASET_DIR}/step4_first_episodes_geometry_{hazard_lower}.json"))

    mock_session = MagicMock()

    def session_get_side_effect(url, *args, **kwargs):
        if "geteventlist" in url and f"eventlist={hazard}" in url:
            return _mock_response(eventlistdata)
        mock_204 = MagicMock()
        mock_204.status_code = 204
        return mock_204

    mock_session.get.side_effect = session_get_side_effect

    def mock_get_side_effect(url, *args, **kwargs):
        if "geteventlist" in url:
            return _mock_response(eventlistdata)
        elif "geteventdata" in url:
            return _mock_response(event_detail_data)
        elif url == step3_url:
            return _mock_response(episode_1_data)
        elif url == step4_url:
            return _mock_response(episode_1_geom_data)
        else:
            return MagicMock(status_code=404)

    with (
        patch("requests.get") as mock_get,
        patch("apps.etl.etl_tasks.segment_gdacs.deep_dive") as mock_deep_dive,
        patch("apps.etl.etl_tasks.gdacs.session", mock_session),
    ):

        def deep_dive_side_effect(session, hazard_type, start_date, end_date, size, extra):
            forced_start = forced_end = datetime.strptime(TEST_DATE, "%Y-%m-%d").date()
            return deep_dive(session, hazard_type, forced_start, forced_end, size, extra)

        mock_deep_dive.side_effect = deep_dive_side_effect
        mock_get.side_effect = mock_get_side_effect

        ext_and_transform_gdacs_latest_data()

    # Only the target hazard processes through the full chain;
    # other hazard types return 204 from session.get so no QUERY is created.
    assert ExtractionData.objects.count() == 4  # QUERY + DETAIL + EPISODE + GEOMETRY
    assert Transform.objects.count() == 1
    assert PyStacLoadData.objects.count() == expected_pystac_count

    expected_output = json.load(open(f"{DATASET_DIR}/{fixed_output_file}", encoding="utf-8"))
    actual_json = json.loads(serialize("json", PyStacLoadData.objects.all()))

    ignore_keys = {
        "created_at",
        "modified_at",
        "monty:etl_id",
        "pk",
        "trace",
        "transform_id",
        "id",
        "href",
        "keywords",
        "links",
    }

    actual_cleaned = remove_ignored_keys(actual_json, ignore_keys)
    expected_cleaned = remove_ignored_keys(expected_output, ignore_keys)
    for expected_item in expected_cleaned:
        assert expected_item in actual_cleaned, f"Expected item not found in actual GDACS output for {fixed_output_file}"
