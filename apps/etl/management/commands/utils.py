import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def validate_dates(start_date: str | None, end_date: str | None):
    """Validate dates"""
    try:
        if start_date and end_date:
            dt_start_date = datetime.strptime(start_date, "%Y-%m-%d")
            dt_end_date = datetime.strptime(end_date, "%Y-%m-%d")
            if dt_start_date > dt_end_date:
                logger.error("Start date cannot be at a later date with respect to End date")
                return (None, None)
        else:
            logger.error("Start date or End date is not specified correctly")
            return (None, None)
    except Exception:
        logger.error("Error occurred while processing the Start/End dates")
        return (None, None)
    return dt_start_date, dt_end_date
