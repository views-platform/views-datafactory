"""HTTP request utilities — retry with exponential backoff.

Shared across datafactory_harvester and datafactory_priogrid.
No outbound imports to other datafactory_* packages.
"""

from __future__ import annotations

import logging
import random
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)


def request_with_retry(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
    json_payload: dict[str, Any] | None = None,
    max_retries: int = 3,
    timeout: int = 30,
) -> requests.Response:
    """HTTP request with exponential backoff retry.

    Args:
        url: URL to request.
        method: HTTP method (GET, POST, etc.).
        headers: Optional HTTP headers.
        params: Optional query parameters.
        data: Optional form-encoded body (POST/PUT).
        json_payload: Optional JSON body (POST/PUT).
        max_retries: Maximum number of attempts.
        timeout: Request timeout in seconds.

    Returns:
        The successful response.

    Raises:
        requests.RequestException: After all retries exhausted.
    """
    for attempt in range(max_retries):
        try:
            resp = requests.request(
                method,
                url,
                headers=headers,
                params=params,
                data=data,
                json=json_payload,
                timeout=timeout,
            )
            resp.raise_for_status()
            return resp
        except requests.HTTPError as exc:
            # 4xx client errors will never succeed on retry — fail fast
            if (
                exc.response is not None
                and 400 <= exc.response.status_code < 500
            ):
                logger.error(
                    "Client error %d (not retryable): %s",
                    exc.response.status_code,
                    url,
                )
                raise
            _retry_or_raise(attempt, max_retries, url)
        except requests.RequestException:
            _retry_or_raise(attempt, max_retries, url)
    msg = "Unreachable"
    raise AssertionError(msg)


def _retry_or_raise(
    attempt: int, max_retries: int, url: str
) -> None:
    """Log and sleep for retry, or raise on final attempt.

    Must be called from an except block — bare raise re-raises
    the caller's active exception.
    """
    if attempt == max_retries - 1:
        logger.error(
            "Request failed after %d attempts: %s",
            max_retries,
            url,
        )
        raise
    delay = 2**attempt + random.uniform(0, 1)
    logger.warning(
        "Request attempt %d/%d failed, retrying in %.1fs",
        attempt + 1,
        max_retries,
        delay,
    )
    time.sleep(delay)
