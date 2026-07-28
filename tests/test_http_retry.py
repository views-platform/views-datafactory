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
    (þing-01 / PLATFORM-001 redaction clause; #369 audit).

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
