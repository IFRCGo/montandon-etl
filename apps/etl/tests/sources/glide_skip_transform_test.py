import copy
import json
from unittest.mock import MagicMock, patch

import json5
import pytest
from django.conf import settings
from django.test import override_settings
from pystac_monty.sources.common import MontyDataTransformer

from apps.etl.etl_tasks.glide import GLIDE_HAZARDS, ext_and_transform_glide_latest_data
from apps.etl.extraction.sources.glide.extract import GlideExtraction
from apps.etl.models import ExtractionData, HazardType, Transform
from apps.etl.tests.common.base_settings_test import TEST_CACHES
from main.configs import etl_config

MontyDataTransformer.base_collection_url = settings.BASE_DIR / "libs/pystac-monty/monty-stac-extension/examples"

GLIDE_HAZARDS_COUNT = len(GLIDE_HAZARDS)
EQ_KEY = HazardType.EARTHQUAKE.value  # "EQ" — the only event type in the test dataset


def _load_payload() -> dict:
    with open(settings.BASE_DIR / "apps/etl/tests/dataset/glide/glide.json5", "r", encoding="utf-8") as f:
        return json5.load(f)


def _records(payload: dict) -> list[dict]:
    return payload["glideset"]


def _hash(payload: dict) -> str | None:
    return GlideExtraction._compute_file_hash(json.dumps(payload).encode("utf-8"))


def _filter_payload_by_events(payload: dict, events: str) -> dict:
    filtered = copy.deepcopy(payload)
    _records(filtered)[:] = [r for r in _records(payload) if r.get("event") == events]
    return filtered


def _run_extraction(payload: dict):
    source_url = f"{etl_config.GLIDE_URL}/glide/jsonglideset.jsp"

    def mock_get(url, **kwargs):
        if url == source_url:
            params = kwargs.get("params")
            events_value = params.events if params else ""
            response = MagicMock()
            response.status_code = 200
            response.content = json.dumps(_filter_payload_by_events(payload, events_value)).encode("utf-8")
            response.headers = {"Content-Type": "application/json"}
            return response
        raise RuntimeError(f"Unexpected URL: {url}")

    with patch("requests.get", side_effect=mock_get):
        ext_and_transform_glide_latest_data()


def _transform_count_by_events(events: str) -> int:
    return Transform.objects.filter(extraction__metadata__params__events=events).count()


def test_compute_file_hash_ignores_unused_fields():
    payload = _load_payload()
    base_hash = _hash(payload)

    # Unused fields and record order should not change the hash
    unchanged = copy.deepcopy(payload)
    _records(unchanged)[0]["homeless"] = 9999
    _records(unchanged)[0]["killed"] = 9999
    _records(unchanged)[0]["affected"] = 9999
    _records(unchanged)[0]["duration"] = 9999
    _records(unchanged)[0]["injured"] = 9999
    _records(unchanged)[0]["time"] = "23:59"
    _records(unchanged)[0]["id"] = "changed-id"
    _records(unchanged)[0]["idsource"] = "changed-idsource"
    _records(unchanged).reverse()
    assert _hash(unchanged) == base_hash

    # No records: no hash
    empty = copy.deepcopy(payload)
    _records(empty).clear()
    assert _hash(empty) is None

    # Fields used by the transformer should change the hash
    changed = copy.deepcopy(payload)
    _records(changed)[0]["magnitude"] = "9.9"
    assert _hash(changed) != base_hash


@pytest.mark.django_db
@override_settings(TRANSFORM_SUCCESS_RATE=20, CELERY_TASK_ALWAYS_EAGER=True, CACHES=TEST_CACHES)
def test_extraction_per_hazard_type():
    _run_extraction(_load_payload())

    # Single extraction for each hazard type
    assert ExtractionData.objects.count() == GLIDE_HAZARDS_COUNT
    events_params = [e.metadata["params"]["events"] for e in ExtractionData.objects.all()]
    assert sorted(events_params) == sorted(h.value for h in GLIDE_HAZARDS)

    # Only EQ has data in the dataset; all others get empty glideset → NO_DATA
    assert _transform_count_by_events(EQ_KEY) == 1
    assert (
        ExtractionData.objects.filter(source_validation_status=ExtractionData.ValidationStatus.NO_DATA).count()
        == GLIDE_HAZARDS_COUNT - 1
    )


@pytest.mark.django_db
@override_settings(TRANSFORM_SUCCESS_RATE=20, CELERY_TASK_ALWAYS_EAGER=True, CACHES=TEST_CACHES)
def test_skip_transform_when_glide_data_not_updated():
    payload = _load_payload()

    # 1. First extraction: transformed
    _run_extraction(payload)
    assert _transform_count_by_events(EQ_KEY) == 1

    # 2. Only unused fields changed: transform skipped
    unchanged = copy.deepcopy(payload)
    _records(unchanged)[0]["homeless"] = 9999
    _records(unchanged)[0]["killed"] = 9999
    _run_extraction(unchanged)
    assert ExtractionData.objects.count() == 2 * GLIDE_HAZARDS_COUNT
    assert _transform_count_by_events(EQ_KEY) == 1
    assert ExtractionData.objects.filter(source_validation_status=ExtractionData.ValidationStatus.NO_CHANGE).count() == 1

    # 3. EQ record changed: EQ is transformed
    changed = copy.deepcopy(payload)
    _records(changed)[0]["magnitude"] = "9.9"
    _run_extraction(changed)
    assert _transform_count_by_events(EQ_KEY) == 2

    # 4. Back to original (A → B → A): EQ transformed because B was the latest loaded data
    _run_extraction(payload)
    assert _transform_count_by_events(EQ_KEY) == 3

    # 5. Transformer version bump: transformed even if data is same
    with override_settings(GLIDE_TRANSFORMER_VERSION="9.9.9"):
        _run_extraction(payload)
    assert _transform_count_by_events(EQ_KEY) == 4


@pytest.mark.django_db
@override_settings(TRANSFORM_SUCCESS_RATE=20, CELERY_TASK_ALWAYS_EAGER=True, CACHES=TEST_CACHES)
def test_ignore_glide_extraction_with_empty_data():
    empty = _load_payload()
    _records(empty).clear()

    # Empty data on consecutive runs: no hash, no revision and no transform
    for run in [1, 2]:
        _run_extraction(empty)
        assert ExtractionData.objects.count() == run * GLIDE_HAZARDS_COUNT
        assert Transform.objects.count() == 0
        assert not ExtractionData.objects.exclude(status=ExtractionData.Status.SUCCESS).exists()
        assert not ExtractionData.objects.exclude(source_validation_status=ExtractionData.ValidationStatus.NO_DATA).exists()
        assert not ExtractionData.objects.filter(file_hash__isnull=False).exists()
        assert not ExtractionData.objects.filter(revision_id__isnull=False).exists()

    # Data available afterwards: transformed
    _run_extraction(_load_payload())
    assert _transform_count_by_events(EQ_KEY) == 1
