import typing

from celery.schedules import crontab


class CeleryBeatSchedule(typing.TypedDict):
    task: str
    schedule: crontab


# FIXME: Use custom formatted cronjobs to define additional configs like sentry monitor thresholds
SCHEDULES: dict[str, CeleryBeatSchedule] = {
    "import_gdacs_data": {
        "task": "apps.etl.etl_tasks.gdacs.ext_and_transform_gdacs_latest_data",
        "schedule": crontab(minute=0, hour=13),
    },
    "import_glide_data": {
        "task": "apps.etl.etl_tasks.glide.ext_and_transform_glide_latest_data",
        "schedule": crontab(minute=0, hour=14),
    },
    "import_emdat_data": {
        "task": "apps.etl.etl_tasks.emdat.ext_and_transform_emdat_latest_data",
        "schedule": crontab(minute=0, hour=15),
    },
    "import_idu_data": {
        "task": "apps.etl.etl_tasks.idu.ext_and_transform_idu_latest_data",
        "schedule": crontab(minute=0, hour=16),
    },
    "import_ifrc_event_data": {
        "task": "apps.etl.etl_tasks.ifrc_event.ext_and_transform_ifrcevent_latest_data",
        "schedule": crontab(minute=0, hour=17),
    },
    "import_gidd_data": {
        "task": "apps.etl.tasks.extract_gidd_data",
        "schedule": crontab(minute=0, hour=18),
    },
    "import_usgs_data": {
        "task": "apps.etl.etl_tasks.usgs.ext_and_transform_usgs_latest_data",
        "schedule": crontab(minute=0, hour=19),
    },
    "import_pdc_data": {
        "task": "apps.etl.tasks.extract_pdc_data",
        "schedule": crontab(minute=30, hour=20),
    },
    "load_data_to_stac": {
        "task": "apps.etl.tasks.load_data",
        "schedule": crontab(minute=0, hour=21),
    },
}
