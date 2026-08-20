import json
from unittest.mock import MagicMock, patch

import pytest
import requests
from django.core.files.base import ContentFile

from apps.etl.extraction.sources.pdc.extract import (
    PDCExposureBatchTask,
    PdcExposureMetadata,
    PDCExtractionMetadata,
    PDCExtractionMetaDataType,
    PDCExtractionV2,
)
from apps.etl.models import ExtractionData
from apps.etl.transform.sources.pdc import PDCTransformHandler

HAZARD_UUID = "62006159-a6da-45d8-b739-8d0940876fa1"


def _make_exposure_detail_extraction(exposure_id: str) -> ExtractionData:
    return PDCExtractionV2.init_extraction(
        metadata=PDCExtractionMetadata(
            url=f"https://sentry.pdc.org/hp_srv/services/hazard/{HAZARD_UUID}/exposure/{exposure_id}",
            type=PDCExtractionMetaDataType.EXPOSURE_DETAIL,
            exposure_detail=PdcExposureMetadata(
                exposure_id=exposure_id,
                hazard_uuid=HAZARD_UUID,
                geojson_id=None,
            ),
        ),
        parent_extraction=None,
        add_to_queue=False,
    )


def _mock_response(data: dict, status_code: int = 200) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.content = json.dumps(data).encode("utf-8")
    response.headers = {"Content-Type": "application/json"}
    if status_code >= 400:
        response.raise_for_status.side_effect = requests.HTTPError(response=response)
    else:
        response.raise_for_status.side_effect = None
    return response


def _make_payload(marker: str, timestamp: str) -> dict:
    return {"hazardUuid": HAZARD_UUID, "impact": marker, "timestamp": timestamp}


@pytest.mark.django_db
def test_compute_exposure_detail_hash_ignores_timestamp():
    payload_a = _make_payload("same", "111")
    payload_b = _make_payload("same", "222")
    payload_c = _make_payload("different", "111")

    hash_a = PDCExposureBatchTask.compute_exposure_detail_hash(json.dumps(payload_a).encode())
    hash_b = PDCExposureBatchTask.compute_exposure_detail_hash(json.dumps(payload_b).encode())
    hash_c = PDCExposureBatchTask.compute_exposure_detail_hash(json.dumps(payload_c).encode())

    assert hash_a == hash_b
    assert hash_a != hash_c


@pytest.mark.django_db
def test_batch_task_skips_transform_for_unchanged_data_and_resets_after_failure():
    # item_1: baseline (A)        -> transform;   revision_id=None
    # item_2: same content (A=T1) -> NO_CHANGE;   revision_id=item_1
    # item_3: content changed (B) -> transform;   revision_id=None
    # item_4: fetch fails (all retries) -> chain preserved (prev stays item_3)
    # item_5: same content (B=T3) -> NO_CHANGE;   revision_id=item_3
    item_1 = _make_exposure_detail_extraction("1000")
    item_2 = _make_exposure_detail_extraction("2000")
    item_3 = _make_exposure_detail_extraction("3000")
    item_4 = _make_exposure_detail_extraction("4000")
    item_5 = _make_exposure_detail_extraction("5000")

    responses_by_exposure_id = {
        "1000": _mock_response(_make_payload("A", "1")),
        "2000": _mock_response(_make_payload("A", "2")),
        "3000": _mock_response(_make_payload("B", "3")),
        "4000": _mock_response({}, status_code=500),
        "5000": _mock_response(_make_payload("B", "5")),
    }

    def mock_get(url, *args, **kwargs):
        exposure_id = url.rsplit("/", 1)[-1]
        return responses_by_exposure_id[exposure_id]

    with (
        patch("requests.get", side_effect=mock_get),
        patch("apps.etl.extraction.sources.pdc.extract.time.sleep"),
        patch.object(PDCTransformHandler.task, "delay") as mock_transform_delay,
    ):
        PDCExposureBatchTask(celery_task=MagicMock()).handle([item_1.pk, item_2.pk, item_3.pk, item_4.pk, item_5.pk])

    item_1.refresh_from_db()
    item_2.refresh_from_db()
    item_3.refresh_from_db()
    item_4.refresh_from_db()
    item_5.refresh_from_db()

    # item_1: transform (no predecessor) -> revision_id not set
    assert item_1.status == ExtractionData.Status.SUCCESS
    assert item_1.source_validation_status != ExtractionData.ValidationStatus.NO_CHANGE

    # item_2: same content as item_1 -> NO_CHANGE; revision_id points to item_1
    assert item_2.status == ExtractionData.Status.SUCCESS
    assert item_2.source_validation_status == ExtractionData.ValidationStatus.NO_CHANGE
    assert item_2.file_hash == item_1.file_hash
    assert item_2.resp_data.name != item_1.resp_data.name
    assert item_2.revision_id == item_1

    # item_3: content changed -> transform; revision_id not set
    assert item_3.status == ExtractionData.Status.SUCCESS
    assert item_3.source_validation_status != ExtractionData.ValidationStatus.NO_CHANGE
    assert item_3.revision_id is None

    # item_4: fetch failed after all retries; hash chain preserved
    assert item_4.status == ExtractionData.Status.FAILED

    # item_5: same content as item_3, chain preserved through item_4's failure -> NO_CHANGE;
    # compared against item_3, revision_id points to item_3
    assert item_5.status == ExtractionData.Status.SUCCESS
    assert item_5.source_validation_status == ExtractionData.ValidationStatus.NO_CHANGE
    assert item_5.file_hash == item_3.file_hash
    assert item_5.revision_id == item_3

    transformed_pks = {call.args[0] for call in mock_transform_delay.call_args_list}
    assert transformed_pks == {item_1.pk, item_3.pk}


@pytest.mark.django_db
def test_batch_task_restores_hash_chain_for_already_successful_items():
    # item_1 was already processed (e.g. on a previous run) and is SUCCESS with a known hash.
    item_1 = _make_exposure_detail_extraction("1000")
    item_1.mark_as_ended(ExtractionData.Status.SUCCESS)
    item_1.file_hash = "deadbeef"
    item_1.save(update_fields=["file_hash"])

    # item_2 is pending and, once fetched, hashes to the same value -> should be skipped.
    item_2 = _make_exposure_detail_extraction("2000")

    with (
        patch(
            "apps.etl.extraction.sources.pdc.extract.PDCExposureBatchTask.compute_exposure_detail_hash",
            return_value="deadbeef",
        ),
        patch("requests.get", side_effect=lambda url, *a, **k: _mock_response(_make_payload("A", "2"))),
        patch.object(PDCTransformHandler.task, "delay") as mock_transform_delay,
    ):
        PDCExposureBatchTask(celery_task=MagicMock()).handle([item_1.pk, item_2.pk])

    item_2.refresh_from_db()
    item_1.refresh_from_db()
    assert item_2.status == ExtractionData.Status.SUCCESS
    assert item_2.source_validation_status == ExtractionData.ValidationStatus.NO_CHANGE
    assert item_2.resp_data.name != item_1.resp_data.name
    assert item_2.revision_id == item_1
    mock_transform_delay.assert_not_called()


@pytest.mark.django_db
def test_handle_exposure_list_skips_when_all_children_already_succeeded():
    exp_list_extraction = PDCExtractionV2.init_extraction(
        metadata=PDCExtractionMetadata(
            url=f"https://sentry.pdc.org/hp_srv/services/hazard/{HAZARD_UUID}/exposure",
            type=PDCExtractionMetaDataType.EXPOSURE_LIST,
            exposure_list={
                "hazard_uuid": HAZARD_UUID,
                "hazard_id": 1,
                "geo_obj_id": None,
            },
        ),
        parent_extraction=None,
        add_to_queue=False,
    )
    exp_list_extraction.resp_data.save("exposure_list.json", ContentFile(json.dumps(["1000"]).encode()))
    exp_list_extraction.mark_as_ended(ExtractionData.Status.SUCCESS)

    already_done = PDCExtractionV2.init_extraction(
        metadata=PDCExtractionMetadata(
            url=f"https://sentry.pdc.org/hp_srv/services/hazard/{HAZARD_UUID}/exposure/1000",
            type=PDCExtractionMetaDataType.EXPOSURE_DETAIL,
            exposure_detail=PdcExposureMetadata(exposure_id="1000", hazard_uuid=HAZARD_UUID, geojson_id=None),
        ),
        parent_extraction=exp_list_extraction,
        add_to_queue=False,
    )
    already_done.mark_as_ended(ExtractionData.Status.SUCCESS)

    with patch("apps.etl.extraction.sources.pdc.extract.group") as mock_group:
        PDCExtractionV2(MagicMock(), exp_list_extraction.pk).handle_exposure_list(retrigger=False, failed_int=None)

    mock_group.assert_not_called()
