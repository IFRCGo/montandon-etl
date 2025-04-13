import logging
import random

from celery import Task

logger = logging.getLogger(__name__)


class RetryableTask(Task):
    @staticmethod
    def exponential_backoff_with_jitter(retries, base_delay=2, min_delay=30, max_delay=1200):
        """
        Calculate delay with exponential backoff, jitter, and min_delay.
        """
        exp_backoff = base_delay * (2**retries)
        jitter = random.uniform(0, 1) * exp_backoff  # Full jitter strategy
        return max(min_delay, min(exp_backoff + jitter, max_delay))
