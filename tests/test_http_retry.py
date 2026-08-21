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
        """Client errors (4xx) fail immediately without retry (C-83)."""
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
        """POST 4xx errors fail immediately, same as GET."""
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
