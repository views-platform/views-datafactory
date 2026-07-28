"""HTTP request utilities — retry with exponential backoff.

Shared across datafactory_harvester and datafactory_priogrid.
No outbound imports to other datafactory_* packages.
"""

from __future__ import annotations

import logging
import random
import time
import urllib.parse
from typing import Any

import requests

logger = logging.getLogger(__name__)

# Query-parameter names whose values are credentials. Some upstream APIs
# (GDL/SHDI) only accept the token as a query param, and requests embeds
# the FULL url — query string included — in exception messages, which
# fail-loud crash tracebacks then carry into log files. Redact at the
# shared layer so no source can leak (PLATFORM-001 redaction clause:
# credentials in any carrier are never logged; endpoints may be).
_SENSITIVE_QUERY_KEYS: frozenset[str] = frozenset({
    "token", "access_token", "apikey", "api_key", "key",
    "password", "secret",
})


def _redact_url(text: str) -> str:
    """Redact credential-bearing query values in any URL inside text.

    Works on plain URLs and on exception messages that embed one
    (requests puts the full url in HTTPError/ConnectionError text).
    """

    def _redact_one(url: str) -> str:
        parsed = urllib.parse.urlsplit(url)
        if not parsed.query:
            return url
        pairs = urllib.parse.parse_qsl(
            parsed.query, keep_blank_values=True,
        )
        redacted = [
            (k, "***" if k.lower() in _SENSITIVE_QUERY_KEYS else v)
            for k, v in pairs
        ]
        return urllib.parse.urlunsplit(
            parsed._replace(
                query=urllib.parse.urlencode(redacted),
            ),
        )

    # Redact query strings wherever they appear, including bare
    # "path?query" fragments in pool-error messages ("Max retries
    # exceeded with url: /api/x?token=..."). Split on whitespace so
    # each candidate is handled independently.
    return " ".join(
        _redact_one(part) if "?" in part else part
        for part in text.split(" ")
    )


def _redacted_copy(
    exc: requests.RequestException,
) -> requests.RequestException:
    """Same exception type with a credential-redacted message.

    Preserves ``response``/``request`` — callers dispatch on
    ``exc.response.status_code`` (ACLED 401 refresh, UCDP 400).
    """
    return type(exc)(
        _redact_url(str(exc)),
        response=exc.response,
        request=exc.request,
    )


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
                    _redact_url(url),
                )
                # from None: the original message (and any chained
                # context requests attached) embeds the full url with
                # query credentials — it must not print in tracebacks.
                raise _redacted_copy(exc) from None
            _retry_or_raise(attempt, max_retries, url, exc)
        except requests.RequestException as exc:
            _retry_or_raise(attempt, max_retries, url, exc)
    msg = "Unreachable"
    raise AssertionError(msg)


def _retry_or_raise(
    attempt: int,
    max_retries: int,
    url: str,
    exc: requests.RequestException,
) -> None:
    """Log and sleep for retry, or raise on final attempt.

    Raises a credential-redacted copy of ``exc`` (same type,
    response/request preserved) rather than re-raising the original,
    whose message may embed the full url with query credentials.
    """
    if attempt == max_retries - 1:
        logger.error(
            "Request failed after %d attempts: %s",
            max_retries,
            _redact_url(url),
        )
        raise _redacted_copy(exc) from None
    delay = 2**attempt + random.uniform(0, 1)
    logger.warning(
        "Request attempt %d/%d failed, retrying in %.1fs",
        attempt + 1,
        max_retries,
        delay,
    )
    time.sleep(delay)
