import json
import typing
from unittest.mock import MagicMock, patch

import pytest
import requests
from django.core.files.base import ContentFile

from apps.etl.extraction.sources.pdc.extract import (
    Pagination,
    PDCExposureBatchTask,
    PDCExposurelistMetadata,
    PdcExposureMetadata,
    PDCExtractionMetadata,
    PDCExtractionMetaDataType,
    PDCExtractionV2,
    PdcHazardInputMetadata,
    PdcPolygonMetadata,
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
def test_batch_task_marks_unchanged_data_and_resets_after_failure():
    # NOTE: Batch task doesn't transform; transform runs once on the EXPOSURE_LIST after all the batches
    # item_1: baseline (A)        -> changed;     revision_id=None
    # item_2: same content (A=T1) -> NO_CHANGE;   revision_id=item_1
    # item_3: content changed (B) -> changed;     revision_id=None
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

    mock_transform_delay.assert_not_called()


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

    with patch("apps.etl.extraction.sources.pdc.extract.chord") as mock_chord:
        PDCExtractionV2(MagicMock(), exp_list_extraction.pk).handle_exposure_list(retrigger=False, failed_int=None)

    mock_chord.assert_not_called()


@pytest.mark.django_db
def test_handle_exposure_list_transforms_once_after_all_batches():
    exp_list_extraction = _make_exposure_list_extraction()
    exp_list_extraction.resp_data.save("exposure_list.json", ContentFile(json.dumps(["1000", "2000", "3000"]).encode()))
    exp_list_extraction.mark_as_ended(ExtractionData.Status.SUCCESS)

    with (
        patch("apps.etl.extraction.sources.pdc.extract.chord") as mock_chord,
        patch.object(PDCExposureBatchTask, "BATCH_SIZE", 2),
    ):
        PDCExtractionV2(MagicMock(), exp_list_extraction.pk).handle_exposure_list(retrigger=False, failed_int=None)

    detail_pks = list(ExtractionData.objects.filter(parent=exp_list_extraction).order_by("id").values_list("pk", flat=True))
    assert len(detail_pks) == 3

    # Header: exposure detail batches
    header = mock_chord.call_args.args[0]
    assert [list(task.args[0]) for task in header] == [detail_pks[:2], detail_pks[2:]]

    # Body: a single transform on the EXPOSURE_LIST (also used when a batch fails)
    body = mock_chord.return_value.call_args.args[0]
    assert body.task == PDCTransformHandler.task.name
    assert tuple(body.args) == (exp_list_extraction.pk,)
    assert body.immutable
    errbacks = body.options["link_error"]
    assert len(errbacks) == 1
    assert errbacks[0]["task"] == PDCTransformHandler.task.name
    assert tuple(errbacks[0]["args"]) == (exp_list_extraction.pk,)


def _make_exposure_list_extraction() -> ExtractionData:
    return PDCExtractionV2.init_extraction(
        metadata=PDCExtractionMetadata(
            url=f"https://sentry.pdc.org/hp_srv/services/hazard/{HAZARD_UUID}/exposure",
            type=PDCExtractionMetaDataType.EXPOSURE_LIST,
            exposure_list=PDCExposurelistMetadata(hazard_uuid=HAZARD_UUID, hazard_id=1, geo_obj_id=None),
        ),
        parent_extraction=None,
        add_to_queue=False,
    )


@pytest.mark.django_db
def test_exposure_list_without_data_still_triggers_transform():
    exp_list_extraction = _make_exposure_list_extraction()

    with (
        patch("requests.get", return_value=_mock_response([])),
        patch.object(PDCTransformHandler.task, "delay") as mock_transform_delay,
    ):
        PDCExtractionV2(MagicMock(), exp_list_extraction.pk).handle()

    exp_list_extraction.refresh_from_db()
    assert exp_list_extraction.status == ExtractionData.Status.SUCCESS
    mock_transform_delay.assert_called_once_with(exp_list_extraction.pk)


def _make_transform_ready_hazard(
    snapshots: list[tuple[str, float, typing.Literal[ExtractionData.Status.SUCCESS, ExtractionData.Status.FAILED], int]],
):
    """
    Create hazard -> (geojson, exposure list -> exposure details) extractions ready for transform.
    snapshots: (exposure_id, timestamp, status, source_validation_status)
    """
    from django.conf import settings

    dataset_dir = settings.BASE_DIR / "apps/etl/tests/dataset/pdc"
    with open(dataset_dir / "exposure_detail.json") as f:
        exposure_detail = json.load(f)

    hazard_extraction = PDCExtractionV2.init_extraction(
        metadata=PDCExtractionMetadata(
            url="https://sentry.pdc.org/hp_srv/services/hazards/t/json/search_hazard",
            type=PDCExtractionMetaDataType.HAZARD,
            hazard=PdcHazardInputMetadata(pagination=Pagination(page=1, pagesize=100), restrictions=[]),
        ),
        parent_extraction=None,
        add_to_queue=False,
    )
    hazard_extraction.resp_data.save("hazard.json", ContentFile((dataset_dir / "hazard_data.json").read_bytes()))
    hazard_extraction.mark_as_ended(ExtractionData.Status.SUCCESS)

    geo_extraction = PDCExtractionV2.init_extraction(
        metadata=PDCExtractionMetadata(
            url="https://sentry.pdc.org/hp_srv/services/mags/1/json/get_mags?hazard_id=1",
            type=PDCExtractionMetaDataType.POLYGON,
            polygon=PdcPolygonMetadata(hazard_uuid=HAZARD_UUID, hazard_id=1, exposure_obj_id=None),
        ),
        parent_extraction=hazard_extraction,
        add_to_queue=False,
    )
    geo_extraction.resp_data.save("geo.json", ContentFile((dataset_dir / "hazard_geo.geojson").read_bytes()))
    geo_extraction.mark_as_ended(ExtractionData.Status.SUCCESS)

    exp_list_extraction = PDCExtractionV2.init_extraction(
        metadata=PDCExtractionMetadata(
            url=f"https://sentry.pdc.org/hp_srv/services/hazard/{HAZARD_UUID}/exposure",
            type=PDCExtractionMetaDataType.EXPOSURE_LIST,
            exposure_list=PDCExposurelistMetadata(hazard_uuid=HAZARD_UUID, hazard_id=1, geo_obj_id=geo_extraction.pk),
        ),
        parent_extraction=hazard_extraction,
        add_to_queue=False,
    )
    exp_list_extraction.resp_data.save("exposure_list.json", ContentFile(json.dumps([s[0] for s in snapshots]).encode()))
    exp_list_extraction.mark_as_ended(ExtractionData.Status.SUCCESS)

    detail_extractions = []
    for exposure_id, timestamp, status, validation_status in snapshots:
        detail = PDCExtractionV2.init_extraction(
            metadata=PDCExtractionMetadata(
                url=f"https://sentry.pdc.org/hp_srv/services/hazard/{HAZARD_UUID}/exposure/{exposure_id}",
                type=PDCExtractionMetaDataType.EXPOSURE_DETAIL,
                exposure_detail=PdcExposureMetadata(
                    exposure_id=exposure_id, hazard_uuid=HAZARD_UUID, geojson_id=geo_extraction.pk
                ),
            ),
            parent_extraction=exp_list_extraction,
            add_to_queue=False,
        )
        if status == ExtractionData.Status.SUCCESS:
            detail.resp_data.save(
                f"exposure_{exposure_id}.json", ContentFile(json.dumps({**exposure_detail, "timestamp": timestamp}).encode())
            )
        detail.source_validation_status = validation_status
        detail.save(update_fields=["source_validation_status"])
        detail.mark_as_ended(status)
        detail_extractions.append(detail)
    return exp_list_extraction, detail_extractions


@pytest.mark.django_db
def test_transform_creates_event_and_hazard_once_for_all_snapshots():
    from django.test import override_settings

    from apps.etl.models import PyStacLoadData, Transform

    success, failed = ExtractionData.Status.SUCCESS, ExtractionData.Status.FAILED
    no_validation, no_change = ExtractionData.ValidationStatus.NO_VALIDATION, ExtractionData.ValidationStatus.NO_CHANGE
    exp_list_extraction, details = _make_transform_ready_hazard(
        [
            ("3000", 1751032300.0, success, no_validation),  # changed
            ("2000", 1751032200.0, success, no_change),  # unchanged: skipped
            ("1500", 1751032150.0, failed, no_validation),  # failed: skipped
            ("1000", 1751032100.0, success, no_validation),  # changed
        ]
    )

    with override_settings(TRANSFORM_SUCCESS_RATE=20):
        # NOTE: Transform of an EXPOSURE_DETAIL (eg: retrigger of older transforms) resolves to its EXPOSURE_LIST
        PDCTransformHandler.task(details[0].pk)

    transforms = Transform.objects.all()
    assert [t.extraction.pk for t in transforms] == [exp_list_extraction.pk]
    assert transforms[0].status == Transform.Status.SUCCESS

    def items_by_type():
        result = {}
        for row in PyStacLoadData.objects.all():
            result.setdefault(row.item_type, []).append(row)
        return result

    rows = items_by_type()
    assert len(rows[PyStacLoadData.ItemType.EVENT]) == 1
    assert len(rows[PyStacLoadData.ItemType.HAZARD]) == 1

    impact_ids = [row.item_id for row in rows[PyStacLoadData.ItemType.IMPACT]]
    assert len(impact_ids) == len(set(impact_ids))
    impact_timestamps = {item_id.split(f"{HAZARD_UUID}-")[1].split("-")[1] for item_id in impact_ids}
    assert impact_timestamps == {"1751032300000", "1751032100000"}

    # Event links to the impact items of all the changed snapshots
    event_item = rows[PyStacLoadData.ItemType.EVENT][0].item
    linked_impacts = {link["href"].rsplit("/", 1)[-1] for link in event_item["links"] if link.get("roles") == ["impact"]}
    assert linked_impacts == set(impact_ids)

    # Re-transform (eg: retrigger) replaces the pending items instead of duplicating them
    with override_settings(TRANSFORM_SUCCESS_RATE=20):
        PDCTransformHandler.task(exp_list_extraction.pk)

    rows_after = items_by_type()
    assert Transform.objects.count() == 1
    assert len(rows_after[PyStacLoadData.ItemType.EVENT]) == 1
    assert len(rows_after[PyStacLoadData.ItemType.HAZARD]) == 1
    assert sorted(row.item_id for row in rows_after[PyStacLoadData.ItemType.IMPACT]) == sorted(impact_ids)
