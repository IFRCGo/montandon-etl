import time
from contextlib import contextmanager

from django.conf import settings
from django.core.cache import caches
from django_redis.client import DefaultClient  # type: ignore[reportMissingTypeStubs]

cache: DefaultClient = caches["default"]  # type: ignore[reportAssignmentType]


class CeleryLock:
    class Key:
        LOAD_TO_STAC = "LOAD_TO_STAC"

    @staticmethod
    @contextmanager
    def redis_lock(lock_id: str, *, lock_expire: int | None = None):
        lock_expire_ = lock_expire or settings.REDIS_LOCK_EXPIRE
        timeout_at: float = time.monotonic() + lock_expire_ - 3
        # cache.add fails if the key already exists
        status = cache.add(lock_id, 1, lock_expire_)
        try:
            yield status
        finally:
            # memcache delete is very slow, but we have to use it to take
            # advantage of using add() for atomic locking
            if time.monotonic() < timeout_at and status:
                # don't release the lock if we exceeded the timeout
                # to lessen the chance of releasing an expired lock
                # owned by someone else
                # also don't release the lock if we didn't acquire it
                cache.delete(lock_id)
