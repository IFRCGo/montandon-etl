class RateLimitError(Exception):
    """Custom exception for rate limit responses (HTTP 429)."""

    def __init__(self, retry_after=None):
        self.retry_after = retry_after
        super().__init__("Rate limit hit (429)")
