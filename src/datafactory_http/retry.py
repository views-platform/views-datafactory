"""HTTP request utilities — retry with exponential backoff.

Shared across datafactory_harvester and datafactory_priogrid.
No outbound imports to other datafactory_* packages.
"""

from __future__ import annotations

import logging
import time

import requests

logger = logging.getLogger(__name__)


def request_with_retry(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    params: dict[str, str | int] | None = None,
    max_retries: int = 3,
    timeout: int = 30,
) -> requests.Response:
    """HTTP GET with exponential backoff retry.

    Args:
        url: URL to request.
        headers: Optional HTTP headers.
        params: Optional query parameters.
        max_retries: Maximum number of attempts.
        timeout: Request timeout in seconds.

    Returns:
        The successful response.

    Raises:
        requests.RequestException: After all retries exhausted.
    """
    for attempt in range(max_retries):
        try:
            resp = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=timeout,
            )
            resp.raise_for_status()
            return resp
        except requests.RequestException:
            if attempt == max_retries - 1:
                logger.error(
                    "Request failed after %d attempts: %s",
                    max_retries,
                    url,
                )
                raise
            delay = 2**attempt
            logger.warning(
                "Request attempt %d/%d failed, retrying in %ds",
                attempt + 1,
                max_retries,
                delay,
            )
            time.sleep(delay)
    msg = "Unreachable"
    raise AssertionError(msg)
