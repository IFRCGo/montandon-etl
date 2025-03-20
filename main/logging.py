import logging

EXTRA_CONTEXT_KEY = "CONTEXT"


def log_render_extra_context(record: logging.LogRecord):
    """
    Append extra->context to logs
    NOTE: This will appear in logs when used with logger.xxx(..., extra={'context': {..content}})
    """
    extra_str = ""
    if extra_raw := getattr(record, EXTRA_CONTEXT_KEY, None):
        extra_str = f" - EXTRA:{str(extra_raw)}"
    record.custom_extra = extra_str
    return True


def log_extra(extra: dict):
    """
    Basic helper function to view extra argument in logs using log_render_extra_context
    """
    return {
        EXTRA_CONTEXT_KEY: extra,
    }
