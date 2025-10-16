from django.conf import settings

TEST_CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": settings.TEST_CACHE_REDIS_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
        "KEY_PREFIX": "test_dj_cache-",
    },
    "local-memory": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    },
}
