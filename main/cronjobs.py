import typing

from celery.schedules import crontab
from sentry_sdk.integrations.celery import beat as sentry_celery_beat


class CeleryBeatSchedule(typing.TypedDict):
    task: str
    schedule: crontab


class CronJobSentryconfig(typing.NamedTuple):
    """
    checkin_margin (min)
    max_runtime (min)
    """

    checkin_margin: int = 5  # In min grace period
    max_runtime: int = 30  # In min
    failure_issue_threshold: int = 1
    recovery_threshold: int = 1


class CronJob(typing.NamedTuple):
    task: str
    schedule: crontab
    sentry_config: CronJobSentryconfig = CronJobSentryconfig()


# NOTE: PeriodicTask will be delete from database if removed from here
SCHEDULES: dict[str, CronJob] = {
    # "import_gdacs_data": CronJob(
    #     task="apps.etl.etl_tasks.gdacs.ext_and_transform_gdacs_latest_data",
    #     schedule=crontab(minute=0, hour=13),
    # ),
    # "import_glide_data": CronJob(
    #     task="apps.etl.etl_tasks.glide.ext_and_transform_glide_latest_data",
    #     schedule=crontab(minute=0, hour=14),
    # ),
    # "import_emdat_data": CronJob(
    #     task="apps.etl.etl_tasks.emdat.ext_and_transform_emdat_latest_data",
    #     schedule=crontab(minute=0, hour=15),
    # ),
    # "import_idu_data": CronJob(
    #     task="apps.etl.etl_tasks.idu.ext_and_transform_idu_latest_data",
    #     schedule=crontab(minute=0, hour=16),
    # ),
    # "import_ifrc_event_data": CronJob(
    #     task="apps.etl.etl_tasks.ifrc_event.ext_and_transform_ifrcevent_latest_data",
    #     schedule=crontab(minute=0, hour=17),
    # ),
    # "import_gidd_data": CronJob(
    #     task="apps.etl.tasks.extract_gidd_data",
    #     schedule=crontab(minute=0, hour=18),
    # ),
    # "import_usgs_data": CronJob(
    #     task="apps.etl.etl_tasks.usgs.ext_and_transform_usgs_latest_data",
    #     schedule=crontab(minute=0, hour=19),
    # ),
    # "import_pdc_data": CronJob(
    #     task="apps.etl.tasks.extract_pdc_data",
    #     schedule=crontab(minute=30, hour=20),
    # ),
    # "load_data_to_stac": CronJob(
    #     task="apps.etl.tasks.load_data",
    #     schedule=crontab(minute=0, hour="*"),  # Every hour
    #     sentry_config=CronJobSentryconfig(
    #         max_runtime=60,
    #         failure_issue_threshold=2,
    #     ),
    # ),
}

BEAT_SCHEDULES: dict[str, CeleryBeatSchedule] = {
    name: {
        "task": config.task,
        "schedule": config.schedule,
    }
    for name, config in SCHEDULES.items()
}


_get_monitor_config = sentry_celery_beat._get_monitor_config


class SentryMonkeyPatch:
    @staticmethod
    def custom__get_monitor_config(celery_schedule, app, monitor_name):
        """
        https://github.com/getsentry/sentry-python/blob/5715734eac1c5fb4b6ec61ef459080c74fa777b5/sentry_sdk/integrations/celery/beat.py#L59
        """
        config = _get_monitor_config(celery_schedule, app, monitor_name)
        job_config = SCHEDULES.get(monitor_name)
        if job_config:
            # Adding additional custom configs
            config.update(
                {
                    "checkin_margin": job_config.sentry_config.checkin_margin,
                    "max_runtime": job_config.sentry_config.max_runtime,
                    "failure_issue_threshold": job_config.sentry_config.failure_issue_threshold,
                    "recovery_threshold": job_config.sentry_config.recovery_threshold,
                }
            )
        return config


sentry_celery_beat._get_monitor_config = SentryMonkeyPatch.custom__get_monitor_config
