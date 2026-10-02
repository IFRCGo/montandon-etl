import copy
import json
from unittest.mock import MagicMock, patch

import json5
import pytest
from django.conf import settings
from django.test import override_settings
from pystac_monty.sources.common import MontyDataTransformer

from apps.etl.etl_tasks.emdat import ext_and_transform_emdat_latest_data
from apps.etl.extraction.sources.emdat.extract import EmdatExtraction
from apps.etl.models import ExtractionData, Transform
from apps.etl.tests.common.base_settings_test import TEST_CACHES
from apps.etl.utils import get_cluster_codes
from main.configs import etl_config

MontyDataTransformer.base_collection_url = settings.BASE_DIR / "libs/pystac-monty/monty-stac-extension/examples"

CLASSIF_KEYS_COUNT = len(get_cluster_codes())
# Classification keys of the records in the dataset: flash flood (7 records) and flood (first record)
FLASH_FLOOD_KEY = "nat-hyd-flo-fla"
FLOOD_KEY = "nat-hyd-flo-flo"


def _load_payload() -> dict:
    with open(settings.BASE_DIR / "apps/etl/tests/dataset/emdat/emdat.json5", "r", encoding="utf-8") as f:
        return json5.load(f)


def _records(payload: dict) -> list[dict]:
    return payload["data"]["public_emdat"]["data"]


def _hash(payload: dict) -> str:
    return EmdatExtraction._compute_file_hash(json.dumps(payload).encode("utf-8"))


def _filter_payload_by_classif(payload: dict, classif_keys: list[str]) -> dict:
    filtered_payload = copy.deepcopy(payload)
    _records(filtered_payload)[:] = [record for record in _records(payload) if record["classif_key"] in classif_keys]
    return filtered_payload


def _run_extraction(payload: dict):
    source_url = f"{etl_config.EMDAT_URL}/v1"

    def mock_post(url, *args, **kwargs):
        assert url == source_url
        classif_keys = kwargs["json"]["variables"]["classif"]
        response = MagicMock()
        response.status_code = 200
        response.content = json.dumps(_filter_payload_by_classif(payload, classif_keys)).encode("utf-8")
        response.headers = {"Content-Type": "application/json"}
        return response

    with patch("requests.post", side_effect=mock_post):
        ext_and_transform_emdat_latest_data()


def _transform_count_by_classif_key() -> dict[str, int]:
    return {
        classif_key: Transform.objects.filter(extraction__metadata__params__classif=[classif_key]).count()
        for classif_key in [FLASH_FLOOD_KEY, FLOOD_KEY]
    }


def test_compute_file_hash_ignores_envelope_and_unused_fields():
    payload = _load_payload()
    base_hash = _hash(payload)

    # Envelope, unused fields and record order should not change the hash
    unchanged = copy.deepcopy(payload)
    unchanged["data"]["public_emdat"]["info"]["timestamp"] = "2030-01-01T00:00:00Z"
    unchanged["data"]["public_emdat"]["total_available"] = 1
    _records(unchanged)[0]["cpi"] = 123.45
    _records(unchanged)[0]["last_update"] = "2030-01-01"
    _records(unchanged).reverse()
    assert _hash(unchanged) == base_hash

    # No records: no hash
    empty = copy.deepcopy(payload)
    _records(empty).clear()
    assert _hash(empty) is None

    # Fields used by the transformer should change the hash
    changed = copy.deepcopy(payload)
    _records(changed)[0]["total_deaths"] = 99999
    assert _hash(changed) != base_hash


@pytest.mark.django_db
@override_settings(TRANSFORM_SUCCESS_RATE=20, CELERY_TASK_ALWAYS_EAGER=True, CACHES=TEST_CACHES)
def test_extraction_per_classif_key():
    _run_extraction(_load_payload())

    # Single extraction for each classification key
    assert ExtractionData.objects.count() == CLASSIF_KEYS_COUNT
    classif_params = [extraction.metadata["params"]["classif"] for extraction in ExtractionData.objects.all()]
    assert sorted(classif_params) == sorted([classif_key] for classif_key in get_cluster_codes())

    # Transformed only the classification keys having data
    assert Transform.objects.count() == 2
    assert _transform_count_by_classif_key() == {FLASH_FLOOD_KEY: 1, FLOOD_KEY: 1}
    assert (
        ExtractionData.objects.filter(source_validation_status=ExtractionData.ValidationStatus.NO_DATA).count()
        == CLASSIF_KEYS_COUNT - 2
    )


@pytest.mark.django_db
@override_settings(TRANSFORM_SUCCESS_RATE=20, CELERY_TASK_ALWAYS_EAGER=True, CACHES=TEST_CACHES)
def test_skip_transform_when_emdat_data_not_updated():
    payload = _load_payload()

    # 1. First extraction: transformed
    _run_extraction(payload)
    assert _transform_count_by_classif_key() == {FLASH_FLOOD_KEY: 1, FLOOD_KEY: 1}

    # 2. Only volatile/unused fields changed: transform skipped
    unchanged = copy.deepcopy(payload)
    unchanged["data"]["public_emdat"]["info"]["timestamp"] = "2030-01-01T00:00:00Z"
    _records(unchanged)[0]["cpi"] = 123.45
    _run_extraction(unchanged)
    assert ExtractionData.objects.count() == 2 * CLASSIF_KEYS_COUNT
    assert _transform_count_by_classif_key() == {FLASH_FLOOD_KEY: 1, FLOOD_KEY: 1}
    assert ExtractionData.objects.filter(source_validation_status=ExtractionData.ValidationStatus.NO_CHANGE).count() == 2

    # 3. Flood record changed: only flood is transformed
    changed = copy.deepcopy(payload)
    assert _records(changed)[0]["classif_key"] == FLOOD_KEY
    _records(changed)[0]["total_deaths"] = 99999
    _run_extraction(changed)
    assert _transform_count_by_classif_key() == {FLASH_FLOOD_KEY: 1, FLOOD_KEY: 2}

    # 4. Back to the original data (A -> B -> A): flood transformed as B is the latest loaded data
    _run_extraction(payload)
    assert _transform_count_by_classif_key() == {FLASH_FLOOD_KEY: 1, FLOOD_KEY: 3}

    # 5. Transformer version bump: transformed even if data is same
    with override_settings(EMDAT_TRANSFORMER_VERSION="9.9.9"):
        _run_extraction(payload)
    assert _transform_count_by_classif_key() == {FLASH_FLOOD_KEY: 2, FLOOD_KEY: 4}


@pytest.mark.django_db
@override_settings(TRANSFORM_SUCCESS_RATE=20, CELERY_TASK_ALWAYS_EAGER=True, CACHES=TEST_CACHES)
def test_ignore_emdat_extraction_with_empty_data():
    empty = _load_payload()
    _records(empty).clear()

    # Empty data on consecutive runs: no hash, no revision and no transform
    for run in [1, 2]:
        _run_extraction(empty)
        assert ExtractionData.objects.count() == run * CLASSIF_KEYS_COUNT
        assert Transform.objects.count() == 0
        assert not ExtractionData.objects.exclude(status=ExtractionData.Status.SUCCESS).exists()
        assert not ExtractionData.objects.exclude(source_validation_status=ExtractionData.ValidationStatus.NO_DATA).exists()
        assert not ExtractionData.objects.filter(file_hash__isnull=False).exists()
        assert not ExtractionData.objects.filter(revision_id__isnull=False).exists()

    # Data available afterwards: transformed
    _run_extraction(_load_payload())
    assert Transform.objects.count() == 2


@pytest.mark.django_db
@override_settings(CELERY_TASK_ALWAYS_EAGER=False)
def test_latest_data_extraction_resumes_failed_classif_key_from_year():
    with patch.object(EmdatExtraction.task, "apply_async"):
        ext_and_transform_emdat_latest_data()
        first_run_extraction_ids = list(ExtractionData.objects.values_list("id", flat=True))
        current_year = ExtractionData.objects.first().metadata["params"]["to"]

        # Mark flood extraction as failed with older from year
        failed_extraction = ExtractionData.objects.get(metadata__params__classif=[FLOOD_KEY])
        failed_extraction.metadata["params"]["from_"] = current_year - 3
        failed_extraction.save(update_fields=["metadata"])
        ExtractionData.objects.update(status=ExtractionData.Status.SUCCESS)
        ExtractionData.objects.filter(id=failed_extraction.id).update(status=ExtractionData.Status.FAILED)

        ext_and_transform_emdat_latest_data()

    latest_from_year_by_classif_key = {
        extraction.metadata["params"]["classif"][0]: extraction.metadata["params"]["from_"]
        for extraction in ExtractionData.objects.exclude(id__in=first_run_extraction_ids)
    }
    assert ExtractionData.objects.count() == 2 * CLASSIF_KEYS_COUNT
    assert latest_from_year_by_classif_key[FLOOD_KEY] == current_year - 3
    assert latest_from_year_by_classif_key[FLASH_FLOOD_KEY] == current_year
