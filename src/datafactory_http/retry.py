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
# shared layer so no source can leak (The Appwrite Seam Contract's
# redaction clause: credentials in any carrier are never logged;
# endpoints may be).
_SENSITIVE_QUERY_KEYS: frozenset[str] = frozenset({
    "token", "access_token", "apikey", "api_key", "key",
    "password", "secret",
})

# Substituted for any URL fragment we cannot parse. Deliberately not the
# original text: a redactor that returns its input on failure emits exactly
# what it exists to suppress.
_UNPARSEABLE_URL = "<unparseable-url-redacted>"


def _redact_url(text: str) -> str:
    """Redact credential-bearing query values in any URL inside text.

    Works on plain URLs and on exception messages that embed one
    (requests puts the full url in HTTPError/ConnectionError text).
    """

    def _redact_one(url: str) -> str:
        try:
            parsed = urllib.parse.urlsplit(url)
            if parsed.username or parsed.password:
                # Userinfo — https://user:pass@host/path. Masked whole
                # rather than password-only: the pair is the credential,
                # and "***:***@" still tells an operator that auth WAS
                # sent, which is the diagnostic the endpoint alone loses.
                host = parsed.hostname or ""
                if parsed.port:
                    host = f"{host}:{parsed.port}"
                parsed = parsed._replace(netloc=f"***:***@{host}")
                url = urllib.parse.urlunsplit(parsed)
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
                    # safe="*" keeps the mask literal. Without it urlencode
                    # emits %2A%2A%2A, and an operator grepping refresh.log
                    # for "token=***" to confirm redaction ran finds nothing.
                    query=urllib.parse.urlencode(redacted, safe="*"),
                ),
            )
        except ValueError:
            # urlsplit raises on malformed authorities — an unbalanced
            # "[" or "]" ("Invalid IPv6 URL"), or a netloc that changes
            # under NFKC normalization. Both are reachable from urllib3
            # connection-pool messages.
            #
            # Failing open here would be worse than not redacting at all:
            # the raise happens while building the argument to
            # _redacted_copy, i.e. INSIDE the except block, so `from None`
            # never executes and Python prints the chained original —
            # credential included — into logs/refresh.log. It would also
            # replace a retryable RequestException with a ValueError that
            # bypasses every harvester's error handling, losing the
            # provenance "failed" ledger entry.
            #
            # So: drop the whole part rather than risk emitting it.
            return _UNPARSEABLE_URL

    # Redact query strings wherever they appear, including bare
    # "path?query" fragments in pool-error messages ("Max retries
    # exceeded with url: /api/x?token=..."). Split on whitespace so
    # each candidate is handled independently.
    #
    # "@" as well as "?": a credential can ride in the userinfo of a URL
    # that has no query string at all, and such a part used to skip the
    # redactor entirely. _redact_one returns its input unchanged when it
    # finds no credential, so widening the filter costs nothing.
    return " ".join(
        _redact_one(part) if ("?" in part or "@" in part) else part
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


# Credential-bearing headers that `requests` does not recognise as
# credentials. On a redirect that changes host it strips only the literal
# "Authorization"; anything else is forwarded to whatever host answers.
# UCDP's token is a custom header, so a 30x from the UCDP API would hand
# a third party a working token (#388 item 7). This is egress, not a log
# leak — redaction cannot help.
#
# Deliberately NOT including "Authorization": requests already strips it,
# and adding it here would change the call kwargs for every ordinary
# authenticated request for no gain.
_CROSS_HOST_UNSAFE_HEADERS: frozenset[str] = frozenset({
    "x-ucdp-access-token",
})


def _carries_custom_credential(headers: dict[str, str] | None) -> bool:
    """True if any header is one requests would forward across hosts."""
    if not headers:
        return False
    return any(
        name.lower() in _CROSS_HOST_UNSAFE_HEADERS for name in headers
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
    # Only constrain redirects for credential-bearing requests. GHSL and
    # GAUL downloads are exactly the kind that move to a CDN, and eleven
    # sources share this function — disabling redirects for all of them
    # would trade a latent egress risk for a live outage.
    redirect_kwargs: dict[str, Any] = {}
    if _carries_custom_credential(headers):
        redirect_kwargs["allow_redirects"] = False

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
                **redirect_kwargs,
            )
            if redirect_kwargs:
                _refuse_redirect(resp, url)
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


def _refuse_redirect(resp: requests.Response, url: str) -> None:
    """Fail loudly rather than follow a redirect with a token in hand.

    ``raise_for_status`` does not fire on 3xx, so without this the
    caller would receive a redirect body and fail somewhere less
    obvious. Following it would be worse: the token would already have
    been sent. Silently dropping the header instead would produce a 401
    from the new host and hide the cause.

    Uses ``status_code`` rather than ``resp.is_redirect`` because a bare
    ``MagicMock`` has a truthy ``is_redirect``, and nine test modules
    patch this call site.
    """
    code = getattr(resp, "status_code", None)
    if not isinstance(code, int) or not (300 <= code < 400):
        return
    target = ""
    headers = getattr(resp, "headers", None)
    if isinstance(headers, dict):
        target = headers.get("Location", "")
    msg = (
        f"Refusing to follow a {code} redirect for a request carrying a "
        f"credential header: {_redact_url(url)} -> "
        f"{_redact_url(target) or '<no Location>'}. The token was NOT "
        f"forwarded. If this endpoint has legitimately moved, update the "
        f"source's base URL rather than allowing the redirect."
    )
    raise requests.RequestException(msg, response=resp)


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
