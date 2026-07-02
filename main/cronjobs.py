import typing

from celery.schedules import crontab
from sentry_sdk.integrations.celery import beat as sentry_celery_beat


class CronJobOption(typing.TypedDict, total=False):
    """Cronjob options"""

    # https://docs.celeryq.dev/en/latest/reference/celery.app.task.html#celery.app.task.Task.apply_async

    expire_seconds: float
    """
    Seconds in the future for the task should expire.
    The task won't be executed after the expiration time.
    """

    time_limit: int
    soft_time_limit: int
    queue: str


class CeleryBeatSchedule(typing.TypedDict):
    task: str
    schedule: crontab
    options: CronJobOption
    args: tuple[typing.Any, ...] | None


class CronJobSentryConfig(typing.NamedTuple):
    """
    checkin_margin (min)
    max_runtime (min)
    """

    checkin_margin: int = 5  # In min grace period
    max_runtime: int = 30  # In min
    failure_issue_threshold: int = 1
    recovery_threshold: int = 1


class TimeConstants:
    """Time constants"""

    SECONDS_IN_A_HOUR = 60 * 60
    SECONDS_IN_A_WEEK = 7 * 24 * 60 * 60
    SECONDS_IN_A_MINUTE = 60
    SECONDS_IN_A_DAY = 24 * 60 * 60
    SECONDS_IN_HALF_DAY = 12 * 60 * 60
    SECONDS_IN_THREE_HOURS = 3 * 60 * 60


class CronJob(typing.NamedTuple):
    """CronJob handler"""

    task: str
    schedule: crontab
    args: tuple[typing.Any, ...] | None = None
    sentry_config: CronJobSentryConfig = CronJobSentryConfig()
    options: CronJobOption = {}


# NOTE: PeriodicTask will be delete from database if removed from here
SCHEDULES: dict[str, CronJob] = {
    "import_pdc_data": CronJob(
        task="apps.etl.etl_tasks.pdc.extract_and_transform_pdc_latest_data",
        schedule=crontab(hour=1, minute=0),
        options=CronJobOption(expire_seconds=TimeConstants.SECONDS_IN_A_DAY),
        sentry_config=CronJobSentryConfig(
            failure_issue_threshold=2,
            checkin_margin=10,
            max_runtime=12 * 60,
        ),
    ),
    "import_emdat_data": CronJob(
        task="apps.etl.etl_tasks.emdat.ext_and_transform_emdat_latest_data",
        schedule=crontab(hour=5, minute=0),
        options=CronJobOption(expire_seconds=TimeConstants.SECONDS_IN_A_DAY),
        sentry_config=CronJobSentryConfig(
            failure_issue_threshold=2,
            checkin_margin=5,
            max_runtime=2 * 60,
        ),
    ),
    "import_glide_data": CronJob(
        task="apps.etl.etl_tasks.glide.ext_and_transform_glide_latest_data",
        schedule=crontab(hour=7, minute=0),
        options=CronJobOption(expire_seconds=TimeConstants.SECONDS_IN_A_DAY),
        sentry_config=CronJobSentryConfig(
            failure_issue_threshold=2,
            checkin_margin=5,
            max_runtime=2 * 60,
        ),
    ),
    "import_gdacs_data": CronJob(
        task="apps.etl.etl_tasks.gdacs.ext_and_transform_gdacs_latest_data",
        schedule=crontab(hour=9, minute=0),
        options=CronJobOption(expire_seconds=TimeConstants.SECONDS_IN_A_DAY),
        sentry_config=CronJobSentryConfig(
            failure_issue_threshold=2,
            checkin_margin=10,
            max_runtime=12 * 60,
        ),
    ),
    "import_ibtracs_data": CronJob(
        task="apps.etl.etl_tasks.noaa_IBTrACS.ext_and_transform_ibtracs_latest_data",
        schedule=crontab(hour=12, minute=0),
        options=CronJobOption(expire_seconds=TimeConstants.SECONDS_IN_A_DAY),
        sentry_config=CronJobSentryConfig(
            failure_issue_threshold=2,
            checkin_margin=5,
            max_runtime=2 * 60,
        ),
    ),
    "import_ifrc_event_data": CronJob(
        task="apps.etl.etl_tasks.ifrc_event.ext_and_transform_ifrcevent_latest_data",
        schedule=crontab(hour=15, minute=0),
        options=CronJobOption(expire_seconds=TimeConstants.SECONDS_IN_A_DAY),
        sentry_config=CronJobSentryConfig(
            failure_issue_threshold=2,
            checkin_margin=5,
            max_runtime=2 * 60,
        ),
    ),
    "import_usgs_data": CronJob(
        task="apps.etl.etl_tasks.usgs.ext_and_transform_usgs_latest_data",
        schedule=crontab(hour=17, minute=0),
        options=CronJobOption(expire_seconds=TimeConstants.SECONDS_IN_A_DAY),
        sentry_config=CronJobSentryConfig(
            failure_issue_threshold=2,
            checkin_margin=10,
            max_runtime=12 * 60,
        ),
    ),
    "import_idu_data": CronJob(
        task="apps.etl.etl_tasks.idu.ext_and_transform_idu_latest_data",
        schedule=crontab(hour=19, minute=0),
        options=CronJobOption(expire_seconds=TimeConstants.SECONDS_IN_A_DAY),
        sentry_config=CronJobSentryConfig(
            failure_issue_threshold=2,
            checkin_margin=5,
            max_runtime=3 * 60,
        ),
    ),
    "import_gidd_data": CronJob(
        task="apps.etl.etl_tasks.gidd.ext_and_transform_gidd_latest_data",
        schedule=crontab(hour=20, minute=0, day_of_week="sunday"),
        options=CronJobOption(expire_seconds=TimeConstants.SECONDS_IN_A_DAY),
        sentry_config=CronJobSentryConfig(
            failure_issue_threshold=2,
            checkin_margin=5,
            max_runtime=3 * 60,
        ),
    ),
    "trigger_pending_extraction": CronJob(
        task="apps.etl.tasks.trigger_pending_extraction",
        schedule=crontab(hour="6,11,16,23", minute=0),
        options=CronJobOption(expire_seconds=TimeConstants.SECONDS_IN_HALF_DAY),
        sentry_config=CronJobSentryConfig(
            failure_issue_threshold=2,
            checkin_margin=10,
            max_runtime=5 * 60,
        ),
    ),
    "load_data_to_stac": CronJob(
        task="apps.etl.tasks.load_data",
        schedule=crontab(hour="*", minute="*/20"),  # Every 20 mins
        sentry_config=CronJobSentryConfig(
            failure_issue_threshold=2,
            checkin_margin=5,
            max_runtime=60,
        ),
        options=CronJobOption(expire_seconds=TimeConstants.SECONDS_IN_A_HOUR),
    ),
    "cleanup_pystac_load_tbl_data": CronJob(
        task="apps.etl.etl_tasks.delete_tbl_rows.cleanup_pystac_load_data",
        schedule=crontab(hour="*/6", minute=0),
        sentry_config=CronJobSentryConfig(
            failure_issue_threshold=2,
            checkin_margin=5,
            max_runtime=180,
        ),
        options=CronJobOption(expire_seconds=TimeConstants.SECONDS_IN_A_HOUR),
    ),
    **{
        f"celery_queue_uptime_{celery_queue_name}": CronJob(
            task="apps.etl.tasks.celery_queue_uptime_check",
            args=(celery_queue_name,),
            schedule=crontab(minute="0", hour="*"),
            options=CronJobOption(expire_seconds=TimeConstants.SECONDS_IN_A_HOUR),
            sentry_config=CronJobSentryConfig(
                failure_issue_threshold=2,
                checkin_margin=2,
                max_runtime=2,
            ),
        )
        for celery_queue_name in ["default", "extraction", "transform", "usgs-extraction"]
        # Note:
        # This list needs to be updated based on what we have
        # in the CeleryQueue in main/celery.py
        # Importing from main/celery.py does not work
        # as there is a cyclic dependency
    },
}


BEAT_SCHEDULES: dict[str, CeleryBeatSchedule] = {
    name: {
        "task": config.task,
        "args": config.args,
        "schedule": config.schedule,
        "options": config.options,
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
