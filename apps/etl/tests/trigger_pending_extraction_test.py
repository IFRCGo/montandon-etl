from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core.cache import caches
from django.test import override_settings
from django.utils import timezone

from apps.etl import tasks
from apps.etl.extraction.sources.gdacs.extract import GdacsExtraction, GdacsExtractionMetadataType
from apps.etl.extraction.sources.glide.extract import GlideExtraction
from apps.etl.models import EtlTrace, ExtractionData
from apps.etl.tests.common.base_settings_test import TEST_CACHES


def _make_pending_extraction(source=ExtractionData.Source.GLIDE, **kwargs) -> ExtractionData:
    obj = ExtractionData.objects.create(
        source=source,
        trace=EtlTrace.objects.create(),
        status=ExtractionData.Status.PENDING,
        attempt_no=0,
        **kwargs,
    )
    # created_at is auto_now_add, only extractions older than two weeks are picked
    ExtractionData.objects.filter(pk=obj.pk).update(created_at=timezone.now() - timedelta(days=20))
    return obj


@pytest.fixture
def test_cache():
    with override_settings(CACHES=TEST_CACHES):
        cache = caches["default"]
        cache.clear()
        with patch.object(tasks, "cache", cache):
            yield cache
        cache.clear()


@pytest.mark.django_db
class TestTriggerPendingExtraction:
    def test_skips_already_queued_extraction(self, test_cache):
        obj = _make_pending_extraction()

        with patch.object(GlideExtraction.task, "apply_async") as apply_async:
            tasks.trigger_pending_extraction()
            tasks.trigger_pending_extraction()

        apply_async.assert_called_once_with(args=(obj.id,), expires=tasks.PENDING_EXTRACTION_MESSAGE_EXPIRE)
        assert test_cache.get(f"{tasks.PENDING_EXTRACTION_QUEUED_KEY_PREFIX}{obj.id}") == 1

    def test_requeues_after_key_expires(self, test_cache):
        obj = _make_pending_extraction()

        with patch.object(GlideExtraction.task, "apply_async") as apply_async:
            tasks.trigger_pending_extraction()
            # Simulate key (and the message) expiring
            test_cache.delete(f"{tasks.PENDING_EXTRACTION_QUEUED_KEY_PREFIX}{obj.id}")
            tasks.trigger_pending_extraction()

        assert apply_async.call_count == 2

    def test_key_outlives_message(self, test_cache):
        obj = _make_pending_extraction()

        with patch.object(GlideExtraction.task, "apply_async"):
            tasks.trigger_pending_extraction()

        ttl = test_cache.ttl(f"{tasks.PENDING_EXTRACTION_QUEUED_KEY_PREFIX}{obj.id}")
        assert tasks.PENDING_EXTRACTION_MESSAGE_EXPIRE < ttl <= tasks.PENDING_EXTRACTION_QUEUED_EXPIRE

    def test_already_queued_does_not_count_towards_limit(self, test_cache):
        queued = _make_pending_extraction()
        not_queued = _make_pending_extraction()
        test_cache.set(f"{tasks.PENDING_EXTRACTION_QUEUED_KEY_PREFIX}{queued.id}", 1)

        with (
            patch.object(tasks, "PENDING_EXTRACTION_TRIGGER_LIMIT", 1),
            patch.object(GlideExtraction.task, "apply_async") as apply_async,
        ):
            tasks.trigger_pending_extraction()

        apply_async.assert_called_once_with(args=(not_queued.id,), expires=tasks.PENDING_EXTRACTION_MESSAGE_EXPIRE)

    def test_nested_extraction_retrigger_passes_expires(self, test_cache):
        parent = _make_pending_extraction(source=ExtractionData.Source.GDACS)
        child = _make_pending_extraction(
            source=ExtractionData.Source.GDACS,
            parent=parent,
            metadata={"type": GdacsExtractionMetadataType.EPISODE},
        )
        # Only the child is under test
        ExtractionData.objects.filter(pk=parent.pk).update(status=ExtractionData.Status.SUCCESS)

        with patch.object(GdacsExtraction.task, "apply_async") as apply_async:
            tasks.trigger_pending_extraction()
            tasks.trigger_pending_extraction()

        apply_async.assert_called_once_with(
            args=(parent.id,),
            kwargs={"retrigger": True, "failed_int": child.id},
            expires=tasks.PENDING_EXTRACTION_MESSAGE_EXPIRE,
        )
