"""Tests for datafactory_http.request_with_retry."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

MOCK_TARGET = "datafactory_http.retry.requests.request"


class TestRequestWithRetryGreen:

    def test_retries_on_failure(self) -> None:
        """Retry with exponential backoff + jitter on transient errors."""
        from datafactory_http import request_with_retry

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()

        with (
            patch(MOCK_TARGET) as mock_request,
            patch(
                "datafactory_http.retry.time.sleep"
            ) as mock_sleep,
            patch(
                "datafactory_http.retry.random.uniform",
                return_value=0.5,
            ),
        ):
            import requests as _req

            mock_request.side_effect = [
                _req.ConnectionError("fail 1"),
                _req.ConnectionError("fail 2"),
                mock_resp,
            ]
            request_with_retry(
                "http://test", max_retries=3, timeout=5
            )

        assert mock_request.call_count == 3
        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(1.5)  # 2^0 + 0.5 jitter
        mock_sleep.assert_any_call(2.5)  # 2^1 + 0.5 jitter

    def test_raises_after_all_retries_exhausted(self) -> None:
        from datafactory_http import request_with_retry

        with (
            patch(MOCK_TARGET) as mock_request,
            patch("datafactory_http.retry.time.sleep"),
        ):
            import requests as _req

            mock_request.side_effect = _req.ConnectionError(
                "always fails"
            )
            with pytest.raises(_req.ConnectionError):
                request_with_retry(
                    "http://test", max_retries=3, timeout=5
                )

        assert mock_request.call_count == 3

    def test_headers_and_params_passed_through(self) -> None:
        """Optional headers and params are forwarded."""
        from datafactory_http import request_with_retry

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()

        with patch(
            MOCK_TARGET,
            return_value=mock_resp,
        ) as mock_request:
            request_with_retry(
                "http://test",
                headers={"Authorization": "token abc"},
                params={"page": 1},
                timeout=10,
            )

        mock_request.assert_called_once_with(
            "GET",
            "http://test",
            headers={"Authorization": "token abc"},
            params={"page": 1},
            data=None,
            json=None,
            timeout=10,
        )

    def test_defaults_no_headers_no_params(self) -> None:
        """Without headers/params, requests.request gets None."""
        from datafactory_http import request_with_retry

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()

        with patch(
            MOCK_TARGET,
            return_value=mock_resp,
        ) as mock_request:
            request_with_retry("http://test", timeout=5)

        mock_request.assert_called_once_with(
            "GET",
            "http://test",
            headers=None,
            params=None,
            data=None,
            json=None,
            timeout=5,
        )

    def test_4xx_not_retried(self) -> None:
        """A 401 fails immediately without retry (C-83).

        Narrowed 2026-10-21: this pins 401, not all of 4xx. 429 is now
        retried (#511, C-72) — see TestRateLimitRetry. The assertions
        below are unchanged; only the claim was too wide, and a reader
        trusting the general version is the drift that let C-72 sit open
        for seven months.
        """
        from datafactory_http import request_with_retry

        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.raise_for_status.side_effect = (
            requests.HTTPError(response=mock_resp)
        )

        with (
            patch(
                MOCK_TARGET,
                return_value=mock_resp,
            ) as mock_request,
            patch("datafactory_http.retry.time.sleep") as mock_sleep,
            pytest.raises(requests.HTTPError),
        ):
            request_with_retry(
                "http://test", max_retries=3, timeout=5
            )

        assert mock_request.call_count == 1  # No retry
        mock_sleep.assert_not_called()

    def test_5xx_still_retried(self) -> None:
        """Server errors (5xx) are retried normally."""
        from datafactory_http import request_with_retry

        fail_resp = MagicMock()
        fail_resp.status_code = 503
        fail_resp.raise_for_status.side_effect = (
            requests.HTTPError(response=fail_resp)
        )

        ok_resp = MagicMock()
        ok_resp.raise_for_status = MagicMock()

        with (
            patch(
                MOCK_TARGET,
                side_effect=[fail_resp, ok_resp],
            ) as mock_request,
            patch("datafactory_http.retry.time.sleep"),
            patch(
                "datafactory_http.retry.random.uniform",
                return_value=0.0,
            ),
        ):
            request_with_retry(
                "http://test", max_retries=3, timeout=5
            )

        assert mock_request.call_count == 2  # Retried once

    def test_default_method_is_get(self) -> None:
        """Without method kwarg, defaults to GET."""
        from datafactory_http import request_with_retry

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()

        with patch(
            MOCK_TARGET, return_value=mock_resp,
        ) as mock_request:
            request_with_retry("http://test", timeout=5)

        assert mock_request.call_args[0][0] == "GET"


class TestRequestWithRetryPost:

    def test_post_method_passed(self) -> None:
        """POST method is forwarded to requests.request."""
        from datafactory_http import request_with_retry

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()

        with patch(
            MOCK_TARGET, return_value=mock_resp,
        ) as mock_request:
            request_with_retry(
                "http://test/token",
                method="POST",
                data={"username": "u", "password": "p"},
                timeout=10,
            )

        mock_request.assert_called_once_with(
            "POST",
            "http://test/token",
            headers=None,
            params=None,
            data={"username": "u", "password": "p"},
            json=None,
            timeout=10,
        )

    def test_post_json_payload(self) -> None:
        """JSON payload is forwarded via the json= kwarg."""
        from datafactory_http import request_with_retry

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()

        with patch(
            MOCK_TARGET, return_value=mock_resp,
        ) as mock_request:
            request_with_retry(
                "http://test/api",
                method="POST",
                json_payload={"key": "value"},
                timeout=5,
            )

        mock_request.assert_called_once_with(
            "POST",
            "http://test/api",
            headers=None,
            params=None,
            data=None,
            json={"key": "value"},
            timeout=5,
        )

    def test_post_4xx_not_retried(self) -> None:
        """A POST 400 fails immediately, same as GET.

        Narrowed 2026-10-21 for the same reason as test_4xx_not_retried:
        this pins 400, not all of 4xx.
        """
        from datafactory_http import request_with_retry

        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.raise_for_status.side_effect = (
            requests.HTTPError(response=mock_resp)
        )

        with (
            patch(
                MOCK_TARGET, return_value=mock_resp,
            ) as mock_request,
            patch("datafactory_http.retry.time.sleep") as mock_sleep,
            pytest.raises(requests.HTTPError),
        ):
            request_with_retry(
                "http://test/token",
                method="POST",
                data={"user": "x"},
                max_retries=3,
                timeout=5,
            )

        assert mock_request.call_count == 1
        mock_sleep.assert_not_called()

    def test_post_5xx_retried(self) -> None:
        """POST 5xx errors are retried."""
        from datafactory_http import request_with_retry

        fail_resp = MagicMock()
        fail_resp.status_code = 502
        fail_resp.raise_for_status.side_effect = (
            requests.HTTPError(response=fail_resp)
        )

        ok_resp = MagicMock()
        ok_resp.raise_for_status = MagicMock()

        with (
            patch(
                MOCK_TARGET,
                side_effect=[fail_resp, ok_resp],
            ) as mock_request,
            patch("datafactory_http.retry.time.sleep"),
            patch(
                "datafactory_http.retry.random.uniform",
                return_value=0.0,
            ),
        ):
            request_with_retry(
                "http://test/token",
                method="POST",
                data={"user": "x"},
                max_retries=3,
                timeout=5,
            )

        assert mock_request.call_count == 2


class TestRequestWithRetryRed:

    def test_timeout_exception_retried(self) -> None:
        """requests.Timeout is retried like other transient errors."""
        from datafactory_http import request_with_retry

        ok_resp = MagicMock()
        ok_resp.raise_for_status = MagicMock()

        with (
            patch(
                MOCK_TARGET,
                side_effect=[
                    requests.Timeout("timed out"),
                    ok_resp,
                ],
            ) as mock_request,
            patch(
                "datafactory_http.retry.time.sleep"
            ) as mock_sleep,
            patch(
                "datafactory_http.retry.random.uniform",
                return_value=0.5,
            ),
        ):
            request_with_retry(
                "http://test", max_retries=3, timeout=5,
            )

        assert mock_request.call_count == 2
        assert mock_sleep.call_count == 1

    def test_http_error_with_no_response_retried(self) -> None:
        """HTTPError with response=None is retried (not 4xx)."""
        from datafactory_http import request_with_retry

        ok_resp = MagicMock()
        ok_resp.raise_for_status = MagicMock()

        with (
            patch(
                MOCK_TARGET,
                side_effect=[
                    requests.HTTPError(response=None),
                    ok_resp,
                ],
            ) as mock_request,
            patch("datafactory_http.retry.time.sleep"),
            patch(
                "datafactory_http.retry.random.uniform",
                return_value=0.0,
            ),
        ):
            request_with_retry(
                "http://test", max_retries=3, timeout=5,
            )

        assert mock_request.call_count == 2


class TestCredentialRedaction:
    """No credential may reach a log line or exception message
    (þing-01 / The Appwrite Seam Contract redaction clause;
    #369 audit).

    GDL/SHDI is the one source that must carry its token as a query
    param; requests embeds the FULL url in exception text, and crash
    tracebacks land in refresh.log. These tests use real exception
    shapes (C-321 rule: fake exception types make error contracts lie).
    """

    def test_redact_url_masks_sensitive_query_values(self) -> None:
        from datafactory_http.retry import _redact_url

        out = _redact_url(
            "https://gdl.test/api/csv?format=csv&token=SECRET123"
        )
        assert "SECRET123" not in out
        assert "format=csv" in out

    def test_redact_url_masks_userinfo_without_a_query(self) -> None:
        """A credential in the URL's userinfo, with no query string.

        The redactor's outer filter only feeds parts containing "?" to
        the per-URL pass, so this URL never reached it at all. #388
        item 6 described this as "does not handle userinfo"; the filter
        is the larger half.
        """
        from datafactory_http.retry import _redact_url

        out = _redact_url("https://alice:s3cret@data.test/grid.zarr")
        assert "s3cret" not in out
        assert "data.test" in out

    def test_redact_url_masks_userinfo_alongside_a_query(self) -> None:
        """Userinfo survived even when the query pass DID run."""
        from datafactory_http.retry import _redact_url

        out = _redact_url(
            "https://alice:s3cret@gdl.test/api?token=SECRET123"
        )
        assert "s3cret" not in out
        assert "SECRET123" not in out

    def test_redact_url_masks_userinfo_inside_an_exception_message(
        self,
    ) -> None:
        """The shape that actually reaches refresh.log."""
        from datafactory_http.retry import _redact_url

        out = _redact_url(
            "HTTPSConnectionPool(host='data.test', port=443): Max "
            "retries exceeded with url: "
            "https://alice:s3cret@data.test/grid.zarr"
        )
        assert "s3cret" not in out
        assert "Max retries exceeded" in out

    def test_redact_url_no_query_unchanged(self) -> None:
        from datafactory_http.retry import _redact_url

        url = "https://ucdpapi.pcr.uu.se/api/gedevents/25.1"
        assert _redact_url(url) == url

    def test_redact_url_handles_embedded_message_urls(self) -> None:
        from datafactory_http.retry import _redact_url

        msg = (
            "401 Client Error: Unauthorized for url: "
            "https://gdl.test/api?format=csv&token=SECRET123"
        )
        out = _redact_url(msg)
        assert "SECRET123" not in out
        assert "401 Client Error" in out

    def test_4xx_raise_is_redacted_and_keeps_response(self) -> None:
        """The fail-fast 4xx path must not leak the token, and must
        preserve .response (ACLED 401-refresh dispatches on it)."""
        from datafactory_http import request_with_retry

        resp = MagicMock()
        resp.status_code = 401
        resp.raise_for_status.side_effect = requests.HTTPError(
            "401 Client Error: Unauthorized for url: "
            "https://gdl.test/api?format=csv&token=SECRET123",
            response=resp,
        )

        with (
            patch(MOCK_TARGET, return_value=resp),
            pytest.raises(requests.HTTPError) as ei,
        ):
            request_with_retry(
                "https://gdl.test/api", max_retries=3, timeout=5,
            )

        assert "SECRET123" not in str(ei.value)
        assert ei.value.response is resp
        # Chained context would print the original (token-bearing)
        # message in tracebacks — must be suppressed.
        assert ei.value.__suppress_context__

    def test_exhausted_retries_raise_is_redacted(self) -> None:
        """ConnectionError text embeds 'url: /path?query' fragments —
        the final raise must redact them and keep the exception type."""
        from datafactory_http import request_with_retry

        err = requests.ConnectionError(
            "HTTPSConnectionPool(host='gdl.test', port=443): "
            "Max retries exceeded with url: "
            "/api/csv?format=csv&token=SECRET123 (Caused by ...)"
        )

        with (
            patch(MOCK_TARGET, side_effect=err),
            patch("datafactory_http.retry.time.sleep"),
            pytest.raises(requests.ConnectionError) as ei,
        ):
            request_with_retry(
                "https://gdl.test/api/csv", max_retries=2, timeout=5,
            )

        assert "SECRET123" not in str(ei.value)
        assert ei.value.__suppress_context__

    # ---- Red: the redactor must never fail open (code review 2026-07-31) ----

    @pytest.mark.parametrize(
        "text",
        [
            # urlsplit raises "Invalid IPv6 URL" on an unbalanced bracket.
            # urllib3 pool messages carry exactly this shape for v6 hosts.
            "Max retries exceeded with url: https://[::1/api?token=SECRET123",
            # urlsplit raises when the netloc changes under NFKC.
            "http://℀a.test/x?token=SECRET123",
            # Degenerate inputs that must not blow up either.
            "",
            "?",
            "a?b",
            "no-scheme.test/x?token=SECRET123",
        ],
    )
    def test_redact_url_never_raises(self, text: str) -> None:
        """_redact_url is called from inside `except` blocks.

        If it raises there, three things go wrong at once: the new
        exception is built while handling the old one, so `from None`
        never runs and Python prints the chained original — credential
        included — into logs/refresh.log; the ValueError is not a
        RequestException, so every harvester's `except` misses it and no
        provenance "failed" entry is written; and the operator sees
        "Invalid IPv6 URL" instead of the real network fault.
        """
        from datafactory_http.retry import _redact_url

        out = _redact_url(text)
        assert "SECRET123" not in out

    def test_redact_url_drops_unparseable_rather_than_echoing(self) -> None:
        """Failing open would emit exactly what this function suppresses."""
        from datafactory_http.retry import _redact_url

        out = _redact_url("https://[::1/api?token=SECRET123")
        assert out == "<unparseable-url-redacted>"

    def test_unparseable_url_does_not_break_the_exception_contract(
        self,
    ) -> None:
        """A malformed URL in the message must still surface as a
        RequestException, not a ValueError from the redactor."""
        from datafactory_http import request_with_retry

        err = requests.ConnectionError(
            "HTTPSConnectionPool(host='::1', port=443): "
            "Max retries exceeded with url: "
            "https://[::1/api?format=csv&token=SECRET123 (Caused by X)"
        )

        with (
            patch(MOCK_TARGET, side_effect=err),
            patch("datafactory_http.retry.time.sleep"),
            pytest.raises(requests.ConnectionError) as ei,
        ):
            request_with_retry(
                "https://gdl.test/api/csv", max_retries=2, timeout=5,
            )

        assert "SECRET123" not in str(ei.value)
        assert ei.value.__suppress_context__

    def test_mask_renders_literally_not_percent_encoded(self) -> None:
        """The placeholder must read `***`, not `%2A%2A%2A`.

        Operators grep refresh.log for `token=***` to confirm redaction
        is running; percent-encoded, that check silently finds nothing.
        Every other test here asserts only that the secret is *absent*,
        which is how the encoded form shipped unnoticed.
        """
        from datafactory_http.retry import _redact_url

        out = _redact_url("https://gdl.test/api?format=csv&token=SECRET123")
        assert "token=***" in out
        assert "%2A" not in out
        # Non-sensitive parameters must survive unmangled.
        assert "format=csv" in out


class TestCrossHostRedirectDoesNotForwardCredentials:
    """A custom credential header must not follow a redirect off-host.

    `requests` strips only the literal ``Authorization`` header when a
    redirect changes host. ``x-ucdp-access-token`` is a custom header,
    so a 30x from the UCDP API to any other host would hand that host
    a working token (#388 item 7). This is egress, not a log leak: no
    amount of redaction helps.
    """

    def test_custom_credential_header_refuses_to_follow_a_redirect(
        self,
    ) -> None:
        from datafactory_http import request_with_retry

        resp = MagicMock()
        resp.status_code = 302
        resp.headers = {"Location": "https://attacker.test/collect"}
        resp.is_redirect = True
        resp.raise_for_status.return_value = None

        with (
            patch(MOCK_TARGET, return_value=resp) as mock_request,
            pytest.raises(requests.RequestException) as ei,
        ):
            request_with_retry(
                "https://ucdpapi.pcr.uu.se/api/gedevents/25.1",
                headers={"x-ucdp-access-token": "SECRET123"},
                max_retries=1,
                timeout=5,
            )

        assert mock_request.call_args[1]["allow_redirects"] is False
        assert "SECRET123" not in str(ei.value)
        assert "attacker.test" in str(ei.value)

    def test_ordinary_request_still_follows_redirects(self) -> None:
        """The guard must not disable redirects for everyone.

        GHSL and GAUL downloads are exactly the kind that move to a
        CDN. Only credential-bearing requests are constrained.
        """
        from datafactory_http import request_with_retry

        resp = MagicMock()
        resp.status_code = 200
        resp.raise_for_status.return_value = None

        with patch(MOCK_TARGET, return_value=resp) as mock_request:
            request_with_retry(
                "https://jeodpp.jrc.ec.europa.eu/ftp/x.zip",
                max_retries=1,
                timeout=5,
            )

        assert "allow_redirects" not in mock_request.call_args[1]


def _response(status: int, headers: dict[str, str] | None = None) -> MagicMock:
    """A failing response whose .headers is a real mapping when given.

    When ``headers`` is None, ``.headers`` is left as the bare MagicMock
    attribute every other test in this file relies on — that is the shape
    that would make ``int(headers.get(...))`` raise TypeError inside the
    except block, so it is a case worth testing rather than avoiding.
    """
    resp = MagicMock()
    resp.status_code = status
    if headers is not None:
        resp.headers = headers
    resp.raise_for_status.side_effect = requests.HTTPError(response=resp)
    return resp


class TestRateLimitRetry:
    """429 is retried; every other 4xx still fails fast (#511, C-72).

    Production incident 2026-10-21 00:07 UTC: the monthly cron aborted at
    step 1/14 when ACLED returned 429 partway through a 71-request cursor
    walk, because request_with_retry classified all of [400, 500) as
    permanent and raised before the retry path was ever reached.
    """

    def test_429_is_retried_then_succeeds(self) -> None:
        """A 429 followed by a 200 completes the request."""
        from datafactory_http import request_with_retry

        ok = MagicMock()
        ok.raise_for_status = MagicMock()

        with (
            patch(MOCK_TARGET) as mock_request,
            patch("datafactory_http.retry.time.sleep") as mock_sleep,
            patch(
                "datafactory_http.retry.random.uniform", return_value=0.0
            ),
        ):
            mock_request.side_effect = [_response(429), ok]
            request_with_retry("http://test", max_retries=3, timeout=5)

        assert mock_request.call_count == 2
        assert mock_sleep.call_count == 1

    def test_429_waits_the_rate_limit_delay_not_the_transport_backoff(
        self,
    ) -> None:
        """A 429 waits a rate-limit window, not the ~1s transport backoff.

        This is the assertion that catches a 429 routed into the generic
        delay. The transport backoff totals ~3s across max_retries=3,
        which would not clear any real burst limit — so a carve-out that
        reached the wrong delay would close C-72 on paper while changing
        nothing in production.
        """
        from datafactory_http import request_with_retry

        with (
            patch(MOCK_TARGET, return_value=_response(429)),
            patch("datafactory_http.retry.time.sleep") as mock_sleep,
            patch(
                "datafactory_http.retry.random.uniform", return_value=0.0
            ),
            pytest.raises(requests.HTTPError),
        ):
            request_with_retry("http://test", max_retries=3, timeout=5)

        mock_sleep.assert_any_call(30.0)  # base * 2^0
        mock_sleep.assert_any_call(60.0)  # base * 2^1
        for call in mock_sleep.call_args_list:
            assert call.args[0] >= 30.0, mock_sleep.call_args_list

    def test_429_exhausted_raises_redacted_error_preserving_response(
        self,
    ) -> None:
        """Exhausting 429 retries still fails loud, with .response intact.

        sources/acled.py dispatches on exc.response.status_code == 401 to
        force a token refresh, so dropping .response here would break
        token renewal, not just a log line.
        """
        from datafactory_http import request_with_retry

        resp = _response(429)
        with (
            patch(MOCK_TARGET, return_value=resp) as mock_request,
            patch("datafactory_http.retry.time.sleep"),
            patch(
                "datafactory_http.retry.random.uniform", return_value=0.0
            ),
            pytest.raises(requests.HTTPError) as exc_info,
        ):
            request_with_retry(
                "http://test?token=SECRET", max_retries=3, timeout=5
            )

        assert mock_request.call_count == 3
        assert exc_info.value.response is resp
        assert exc_info.value.__suppress_context__
        assert "SECRET" not in str(exc_info.value)

    def test_retry_after_seconds_is_honoured(self) -> None:
        """A usable Retry-After overrides the computed backoff exactly."""
        from datafactory_http import request_with_retry

        ok = MagicMock()
        ok.raise_for_status = MagicMock()

        with (
            patch(MOCK_TARGET) as mock_request,
            patch("datafactory_http.retry.time.sleep") as mock_sleep,
            patch(
                "datafactory_http.retry.random.uniform", return_value=0.0
            ),
        ):
            mock_request.side_effect = [
                _response(429, {"Retry-After": "45"}),
                ok,
            ]
            request_with_retry("http://test", max_retries=3, timeout=5)

        # 45, not 30: the server named a time, so no jitter is added.
        mock_sleep.assert_any_call(45.0)
        assert 30.0 not in [c.args[0] for c in mock_sleep.call_args_list]

    def test_retry_after_is_read_from_a_case_insensitive_dict(self) -> None:
        """The header is read off the type requests actually supplies.

        A real response carries a CaseInsensitiveDict, which subclasses
        MutableMapping and is NOT a dict. A `isinstance(headers, dict)`
        guard would be False in production while passing every test that
        uses a plain dict — a guard that cannot fire. This test pins the
        production type and lowercases the key to prove the lookup is
        case-insensitive, as HTTP headers are.
        """
        from datafactory_http import request_with_retry

        ok = MagicMock()
        ok.raise_for_status = MagicMock()
        headers = requests.structures.CaseInsensitiveDict(
            {"retry-after": "45"}
        )

        with (
            patch(MOCK_TARGET) as mock_request,
            patch("datafactory_http.retry.time.sleep") as mock_sleep,
            patch(
                "datafactory_http.retry.random.uniform", return_value=0.0
            ),
        ):
            mock_request.side_effect = [_response(429, headers), ok]
            request_with_retry("http://test", max_retries=3, timeout=5)

        mock_sleep.assert_any_call(45.0)

    def test_retry_after_above_the_ceiling_fails_fast(self) -> None:
        """A quota-scale Retry-After is refused, not slept through.

        Cloudflare-fronted 429s routinely carry 3600 or 86400. Honouring
        one stalls an unattended monthly cron for a day, which ADR-011
        forbids more clearly than it forbids retrying. The refusal names
        the value so raising the ceiling later is evidence-backed.
        """
        from datafactory_http import request_with_retry

        with (
            patch(
                MOCK_TARGET,
                return_value=_response(429, {"Retry-After": "3600"}),
            ) as mock_request,
            patch("datafactory_http.retry.time.sleep") as mock_sleep,
            pytest.raises(requests.HTTPError) as exc_info,
        ):
            request_with_retry("http://test", max_retries=3, timeout=5)

        assert mock_request.call_count == 1
        mock_sleep.assert_not_called()
        assert "3600" in str(exc_info.value)

    @pytest.mark.parametrize(
        "raw",
        [
            "soon",
            "",
            "-5",
            "0",
            "45.5",
            "Wed, 21 Oct 2026 07:28:00 GMT",
            "nan",
            "1e9999",
        ],
    )
    def test_unusable_retry_after_falls_back_to_backoff(
        self, raw: str
    ) -> None:
        """Nothing in a hostile header reaches time.sleep or escapes.

        "-5" would make time.sleep raise ValueError; "nan"/"1e9999" would
        sleep for a nonsense duration if parsed as float; the HTTP-date
        form is legal per RFC 9110 and deliberately unparsed. All fall
        back to the computed wait, and the call still fails loud.
        """
        from datafactory_http import request_with_retry

        with (
            patch(
                MOCK_TARGET,
                return_value=_response(429, {"Retry-After": raw}),
            ),
            patch("datafactory_http.retry.time.sleep") as mock_sleep,
            patch(
                "datafactory_http.retry.random.uniform", return_value=0.0
            ),
            pytest.raises(requests.HTTPError),
        ):
            request_with_retry("http://test", max_retries=3, timeout=5)

        mock_sleep.assert_any_call(30.0)

    def test_429_with_mock_headers_does_not_crash(self) -> None:
        """A non-mapping .headers must not raise from inside except.

        int(MagicMock()) raises TypeError. Raised from the except block it
        would escape where `from None` cannot run, printing the chained
        original message — which embeds the full url including query
        credentials. Every other response in this file has exactly this
        shape, which is why it is the likeliest real failure here.
        """
        from datafactory_http import request_with_retry

        with (
            patch(MOCK_TARGET, return_value=_response(429)),
            patch("datafactory_http.retry.time.sleep") as mock_sleep,
            patch(
                "datafactory_http.retry.random.uniform", return_value=0.0
            ),
            pytest.raises(requests.HTTPError) as exc_info,
        ):
            request_with_retry(
                "http://test?token=SECRET", max_retries=3, timeout=5
            )

        assert not isinstance(exc_info.value, TypeError)
        assert "SECRET" not in str(exc_info.value)
        mock_sleep.assert_any_call(30.0)

    def test_429_with_headers_lacking_get_does_not_crash(self) -> None:
        """The mapping guard's own job, isolated.

        test_429_with_mock_headers_does_not_crash does not isolate it: a
        MagicMock has .get, so the `isinstance(raw, str)` check downstream
        already stops int() from seeing a MagicMock. What the mapping
        check independently prevents is a .headers with no .get at all —
        an AttributeError raised from inside the except block, which
        escapes where `from None` cannot run and prints the chained
        original message with the url's query credentials in it.

        Drilled: removing the mapping check turns this red, and nothing
        else in the suite notices.
        """
        from datafactory_http import request_with_retry

        resp = _response(429)
        resp.headers = []  # has no .get

        with (
            patch(MOCK_TARGET, return_value=resp),
            patch("datafactory_http.retry.time.sleep") as mock_sleep,
            patch(
                "datafactory_http.retry.random.uniform", return_value=0.0
            ),
            pytest.raises(requests.HTTPError) as exc_info,
        ):
            request_with_retry(
                "http://test?token=SECRET", max_retries=3, timeout=5
            )

        assert "SECRET" not in str(exc_info.value)
        mock_sleep.assert_any_call(30.0)

    def test_the_ceiling_bounds_the_wait_jitter_included(self) -> None:
        """120s is the ceiling, so nothing may sleep 125s.

        Jitter was added AFTER the clamp, so the real bound was
        ``_RATE_LIMIT_MAX_WAIT_S + _RATE_LIMIT_JITTER_S`` = 125s, while
        the constant's own comment called itself "the longest wait this
        layer will ever perform". Worse, the number was being read two
        ways at once: a server asking for 121s was REFUSED as a quota
        block while the layer would sleep 125s of its own accord.

        Driven at the maximum jitter rather than a random draw, because a
        bound is not tested by a sample from inside it.

        Mutation: move ``random.uniform`` back outside ``min(...)``. This
        test goes red at 125.0 > 120.0.

        Found by independent review of PR #521, not by the author.
        """
        from datafactory_http import request_with_retry
        from datafactory_http.retry import _RATE_LIMIT_MAX_WAIT_S

        with (
            patch(MOCK_TARGET, return_value=_response(429)),
            patch("datafactory_http.retry.time.sleep") as mock_sleep,
            # The top of the jitter range, not a sample from inside it.
            patch(
                "datafactory_http.retry.random.uniform", return_value=5.0
            ),
            pytest.raises(requests.HTTPError),
        ):
            request_with_retry("http://test", max_retries=8, timeout=5)

        assert mock_sleep.call_args_list, "nothing slept; test is vacuous"
        for call in mock_sleep.call_args_list:
            assert call.args[0] <= _RATE_LIMIT_MAX_WAIT_S, (
                f"slept {call.args[0]}s against a "
                f"{_RATE_LIMIT_MAX_WAIT_S}s ceiling: "
                f"{mock_sleep.call_args_list}"
            )

    def test_no_rate_limit_wait_is_computed_on_the_final_attempt(
        self, caplog: pytest.LogCaptureFixture,
    ) -> None:
        """The last attempt retries nothing, so it must claim nothing.

        ``_rate_limit_delay`` has two side effects — it logs the
        Retry-After it observed, and it raises when the server asks for
        more than the ceiling. Passed eagerly as an argument to
        ``_retry_or_raise``, both fired on the FINAL attempt, where no
        retry follows. Two consequences, in a release whose whole subject
        is making a failure say why: a WARNING announcing a retry that
        never happened, and — when Retry-After exceeded the ceiling — the
        ceiling error raised INSTEAD of the exhaustion path, so the log
        never named retry exhaustion as the cause.

        Asserted on the log rather than on a call count because the log
        line is what an operator reads at 02:00.

        Mutation: pass ``delay=_rate_limit_delay(exc, url, attempt)``
        eagerly again instead of ``rate_limited=True``. This test goes
        red — a third "Rate limited" line appears for max_retries=3.

        Found by independent review of PR #521, not by the author.
        """
        import logging

        from datafactory_http import request_with_retry

        with (
            patch(MOCK_TARGET, return_value=_response(429)),
            patch("datafactory_http.retry.time.sleep"),
            patch(
                "datafactory_http.retry.random.uniform", return_value=0.0
            ),
            caplog.at_level(logging.WARNING, logger="datafactory_http"),
            pytest.raises(requests.HTTPError),
        ):
            request_with_retry("http://test", max_retries=3, timeout=5)

        rate_limited = [
            r for r in caplog.records if "Rate limited" in r.getMessage()
        ]
        assert len(rate_limited) == 2, (
            "expected one Rate-limited line per attempt that actually "
            "retries (2 of 3), got "
            f"{[r.getMessage() for r in rate_limited]}"
        )
        assert any(
            "failed after 3 attempts" in r.getMessage()
            for r in caplog.records
        ), (
            "the final attempt must name retry exhaustion as the cause: "
            f"{[r.getMessage() for r in caplog.records]}"
        )

    def test_403_still_fails_fast(self) -> None:
        """The carve-out is exactly one status wide.

        No pre-existing test pinned 403 or 404, so nothing stopped the
        retryable set widening. Some providers do rate-limit with 403;
        here a 403 is a credential or scope fault and retrying one only
        burns the wait to re-learn it.
        """
        from datafactory_http import request_with_retry

        with (
            patch(MOCK_TARGET, return_value=_response(403)) as mock_request,
            patch("datafactory_http.retry.time.sleep") as mock_sleep,
            pytest.raises(requests.HTTPError),
        ):
            request_with_retry("http://test", max_retries=3, timeout=5)

        assert mock_request.call_count == 1
        mock_sleep.assert_not_called()

    def test_404_still_fails_fast(self) -> None:
        """Companion to the 403 case; also previously unpinned."""
        from datafactory_http import request_with_retry

        with (
            patch(MOCK_TARGET, return_value=_response(404)) as mock_request,
            patch("datafactory_http.retry.time.sleep") as mock_sleep,
            pytest.raises(requests.HTTPError),
        ):
            request_with_retry("http://test", max_retries=3, timeout=5)

        assert mock_request.call_count == 1
        mock_sleep.assert_not_called()

    def test_429_log_line_names_the_retry_after_value(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """The measurement hook gets a guard of its own.

        ACLED's rate-limit window is unmeasured and the fallback constant
        is borrowed from UCDP, because the branch this change replaced
        logged only the status code. This log line is what will calibrate
        it on the next real 429, so it must not be silently dropped.
        """
        import logging

        from datafactory_http import request_with_retry

        ok = MagicMock()
        ok.raise_for_status = MagicMock()

        with (
            caplog.at_level(logging.WARNING, logger="datafactory_http.retry"),
            patch(MOCK_TARGET) as mock_request,
            patch("datafactory_http.retry.time.sleep"),
            patch(
                "datafactory_http.retry.random.uniform", return_value=0.0
            ),
        ):
            mock_request.side_effect = [
                _response(429, {"Retry-After": "45"}),
                ok,
            ]
            request_with_retry("http://test", max_retries=3, timeout=5)

        assert "45s" in caplog.text, caplog.text

        caplog.clear()
        with (
            caplog.at_level(logging.WARNING, logger="datafactory_http.retry"),
            patch(MOCK_TARGET) as mock_request,
            patch("datafactory_http.retry.time.sleep"),
            patch(
                "datafactory_http.retry.random.uniform", return_value=0.0
            ),
        ):
            mock_request.side_effect = [_response(429), ok]
            request_with_retry("http://test", max_retries=3, timeout=5)

        assert "absent" in caplog.text, caplog.text
