"""HTTP request utilities — retry with exponential backoff.

No outbound imports to other datafactory_* packages.
"""

from datafactory_http.retry import request_with_retry

__all__ = [
    "request_with_retry",
]
