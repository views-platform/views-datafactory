"""HTTP request utilities — retry with exponential backoff.

Shared across datafactory_harvester and datafactory_priogrid.
No outbound imports to other datafactory_* packages.
"""

from __future__ import annotations

import logging
import random
import time
import urllib.parse
from collections.abc import Mapping
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

# The one 4xx that means "later", not "never". A rate limiter is the server
# asking us to slow down; the request itself was valid, which is why ACLED
# returned seventy pages before the one that failed (#511, 2026-10-21).
#
# A frozenset rather than `== 429` so the neighbouring answers live next to
# the data instead of in a commit message:
#   408 is OUT. It means the server stopped waiting for OUR request; the
#       client-side form of that fault already arrives as requests.Timeout
#       and is already retried. No 408 has ever been observed here, so a
#       408 test could only stand in for a hypothesis — and the rate-limit
#       delay below would be the wrong delay for it.
#   403 is OUT. Some providers rate-limit with 403, but here a 403 is a
#       credential or scope fault, and retrying one burns the wait twice
#       over to re-learn it.
#
# Members are rate-limit statuses specifically: the delay policy below is
# sized to a rate-limit window. A status that is retryable for some other
# reason would need its own delay, not this one.
_RETRYABLE_CLIENT_STATUSES: frozenset[int] = frozenset({429})

# Fallback wait when the server does not say how long. BORROWED, NOT
# MEASURED: the only rate window observed anywhere in this repo is UCDP's
# ~1 minute (sources/ucdp_annual.py). ACLED's is unknown, because the
# fail-fast branch this change replaces logged only the status code, so the
# 2026-10-21 incident never recorded whether a Retry-After header arrived.
# The WARNING in _rate_limit_delay exists to capture that on the next 429,
# which is what makes this number self-correcting rather than folklore.
_RATE_LIMIT_BASE_DELAY_S: float = 30.0

# Mirrors UCDP's window-scale jitter. At concurrency 1 this decorrelates
# nothing; it is here because ADR-018's Timeout Policy states
# backoff-with-jitter as doctrine, and a reader comparing the two paths
# should not have to wonder why one of them lacks it.
_RATE_LIMIT_JITTER_S: float = 5.0

# Two readings of one number, both deliberate. It is the longest wait this
# layer will ever perform, so the computed backoff is clamped to it. And a
# server asking for MORE than our maximum wait is declaring a quota block
# rather than a burst — Cloudflare-fronted 429s routinely carry 3600 or
# 86400, and honouring one would stall an unattended monthly cron for a
# day, which ADR-011 forbids far more clearly than it forbids retrying. So
# a larger Retry-After fails loud, naming the value, which makes raising
# this ceiling later a one-line change with evidence behind it.
#
# 120s is twice the only rate window measured in this repo (UCDP, ~1 min)
# and twice ACLED's own 60s read timeout.
_RATE_LIMIT_MAX_WAIT_S: float = 120.0


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
            # getattr + isinstance rather than `exc.response is not None`
            # and a bare comparison, for the reason _refuse_redirect gives
            # below: a bare MagicMock is truthy everywhere, nine test
            # modules patch this call site, and a non-int status would
            # raise TypeError here — inside the except block, where
            # `from None` cannot run and the chained token-bearing message
            # prints.
            code = getattr(exc.response, "status_code", None)
            if isinstance(code, int) and code in _RETRYABLE_CLIENT_STATUSES:
                # Rate limiting is the one 4xx worth waiting out. See
                # _RETRYABLE_CLIENT_STATUSES for why this set has one
                # member, and ADR-027's 2026-10-21 amendment for why this
                # lives here rather than at each pagination layer: the
                # pagination-context argument holds for AMBIGUOUS statuses
                # (UCDP signals rate limits as 400, which could mean
                # anything), and 429 is never ambiguous.
                _retry_or_raise(
                    attempt,
                    max_retries,
                    url,
                    exc,
                    delay=_rate_limit_delay(exc, url, attempt),
                )
            # Every other 4xx will never succeed on retry — fail fast
            elif isinstance(code, int) and 400 <= code < 500:
                logger.error(
                    "Client error %d (not retryable): %s",
                    code,
                    _redact_url(url),
                )
                # from None: the original message (and any chained
                # context requests attached) embeds the full url with
                # query credentials — it must not print in tracebacks.
                raise _redacted_copy(exc) from None
            else:
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


def _retry_after_seconds(resp: requests.Response | None) -> int | None:
    """Parse ``Retry-After`` as delta-seconds, or None if unusable.

    None for absent, non-mapping headers, non-numeric text, an HTTP-date,
    or a value <= 0. Every one of those falls back to the computed backoff
    rather than failing, because a slightly wrong wait is recoverable and
    an exception raised from inside an ``except`` block is not.

    ``Mapping``, not ``dict``: every real ``requests`` response carries a
    ``CaseInsensitiveDict``, which subclasses ``MutableMapping`` and is
    *not* a ``dict`` — an ``isinstance(headers, dict)`` guard here would be
    False in production while every unit test passed on a plain dict, i.e.
    a guard that cannot fire. A bare ``MagicMock`` is not a ``Mapping``
    either, so this still refuses one. That matters because
    ``int(MagicMock())`` raises ``TypeError`` from inside the ``except``
    block, where ``from None`` cannot run and the chained, token-bearing
    original message would print — the same hazard ``_refuse_redirect``
    guards against, and every response in tests/test_http_retry.py is a
    ``MagicMock``.

    RFC 9110 §10.2.3 also permits an HTTP-date, which is deliberately not
    parsed: that means reasoning about the provider's clock against ours
    inside an error path, and a skewed date yields an absurd sleep. An
    unparsed date costs nothing — it falls back to a real wait. If a
    capture ever shows a provider sending dates, ``parsedate_to_datetime``
    is a two-line change with evidence behind it.
    """
    headers = getattr(resp, "headers", None)
    if not isinstance(headers, Mapping):
        return None
    raw = headers.get("Retry-After")
    if not isinstance(raw, str):
        return None
    try:
        # int, not float: rejects nan, inf and 1e9999 by construction
        # rather than by three more comparisons. "45.5" falling back to
        # the computed backoff is an acceptable loss.
        seconds = int(raw.strip())
    except (TypeError, ValueError):
        return None
    # Retry-After: 0 is legal but means an instant retry into a rate
    # limiter, and a negative value would make time.sleep raise.
    return seconds if seconds > 0 else None


def _rate_limit_delay(
    exc: requests.HTTPError,
    url: str,
    attempt: int,
) -> float:
    """Seconds to wait before retrying a rate-limited request.

    Honours ``Retry-After`` when usable, falls back to a
    rate-limit-scale backoff when it is not, and raises when the server
    asks for longer than this layer will ever wait.

    Raises:
        requests.HTTPError: Redacted, when the requested wait exceeds
            ``_RATE_LIMIT_MAX_WAIT_S``.
    """
    requested = _retry_after_seconds(exc.response)
    # The measurement this change exists to start collecting. The branch
    # it replaces logged only the status code, so we still do not know
    # whether ACLED sends this header at all.
    logger.warning(
        "Rate limited (429) on attempt %d, Retry-After: %s",
        attempt + 1,
        "absent" if requested is None else f"{requested}s",
    )
    if requested is None:
        # 2.0, not 2: mypy types `int ** int` as Any, because a negative
        # exponent returns a float.
        return min(
            _RATE_LIMIT_BASE_DELAY_S * 2.0**attempt,
            _RATE_LIMIT_MAX_WAIT_S,
        ) + random.uniform(0, _RATE_LIMIT_JITTER_S)
    if requested > _RATE_LIMIT_MAX_WAIT_S:
        logger.error(
            "Rate limited, Retry-After %ds exceeds the %.0fs ceiling "
            "(not retryable): %s",
            requested,
            _RATE_LIMIT_MAX_WAIT_S,
            _redact_url(url),
        )
        # Same redaction contract as _redacted_copy — same type, response
        # and request preserved, message passed through _redact_url — with
        # the refused value appended so raising the ceiling later is an
        # evidence-backed change rather than a guess.
        msg = (
            f"{_redact_url(str(exc))} (Retry-After: {requested}s exceeds "
            f"the {_RATE_LIMIT_MAX_WAIT_S:.0f}s ceiling)"
        )
        raise type(exc)(
            msg, response=exc.response, request=exc.request
        ) from None
    # No jitter: the server named a time, so wait exactly that long.
    return float(requested)


def _retry_or_raise(
    attempt: int,
    max_retries: int,
    url: str,
    exc: requests.RequestException,
    *,
    delay: float | None = None,
) -> None:
    """Log and sleep for retry, or raise on final attempt.

    Raises a credential-redacted copy of ``exc`` (same type,
    response/request preserved) rather than re-raising the original,
    whose message may embed the full url with query credentials.

    Args:
        delay: Seconds to wait, for callers whose wait is set by policy
            rather than by transport backoff (rate limiting). None means
            use the transport backoff below. Parameterised rather than
            duplicated because the part that would be duplicated is the
            terminal raise above — the one block in this module where a
            divergent copy leaks a credential.
    """
    if attempt == max_retries - 1:
        logger.error(
            "Request failed after %d attempts: %s",
            max_retries,
            _redact_url(url),
        )
        raise _redacted_copy(exc) from None
    if delay is None:
        delay = 2**attempt + random.uniform(0, 1)
    logger.warning(
        "Request attempt %d/%d failed, retrying in %.1fs",
        attempt + 1,
        max_retries,
        delay,
    )
    time.sleep(delay)
