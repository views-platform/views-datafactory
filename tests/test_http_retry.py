"""Tests for datafactory_http.request_with_retry."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests


class TestRequestWithRetryGreen:

    def test_retries_on_failure(self) -> None:
        """Retry with exponential backoff + jitter on transient errors."""
        from datafactory_http import request_with_retry

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()

        with (
            patch(
                "datafactory_http.retry.requests.get"
            ) as mock_get,
            patch(
                "datafactory_http.retry.time.sleep"
            ) as mock_sleep,
            patch(
                "datafactory_http.retry.random.uniform",
                return_value=0.5,
            ),
        ):
            import requests as _req

            mock_get.side_effect = [
                _req.ConnectionError("fail 1"),
                _req.ConnectionError("fail 2"),
                mock_resp,
            ]
            request_with_retry(
                "http://test", max_retries=3, timeout=5
            )

        assert mock_get.call_count == 3
        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(1.5)  # 2^0 + 0.5 jitter
        mock_sleep.assert_any_call(2.5)  # 2^1 + 0.5 jitter

    def test_raises_after_all_retries_exhausted(self) -> None:
        from datafactory_http import request_with_retry

        with (
            patch(
                "datafactory_http.retry.requests.get"
            ) as mock_get,
            patch("datafactory_http.retry.time.sleep"),
        ):
            import requests as _req

            mock_get.side_effect = _req.ConnectionError("always fails")
            with pytest.raises(_req.ConnectionError):
                request_with_retry(
                    "http://test", max_retries=3, timeout=5
                )

        assert mock_get.call_count == 3

    def test_headers_and_params_passed_through(self) -> None:
        """Optional headers and params are forwarded to requests.get."""
        from datafactory_http import request_with_retry

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()

        with patch(
            "datafactory_http.retry.requests.get",
            return_value=mock_resp,
        ) as mock_get:
            request_with_retry(
                "http://test",
                headers={"Authorization": "token abc"},
                params={"page": 1},
                timeout=10,
            )

        mock_get.assert_called_once_with(
            "http://test",
            headers={"Authorization": "token abc"},
            params={"page": 1},
            timeout=10,
        )

    def test_defaults_no_headers_no_params(self) -> None:
        """Without headers/params, requests.get gets None for both."""
        from datafactory_http import request_with_retry

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()

        with patch(
            "datafactory_http.retry.requests.get",
            return_value=mock_resp,
        ) as mock_get:
            request_with_retry("http://test", timeout=5)

        mock_get.assert_called_once_with(
            "http://test",
            headers=None,
            params=None,
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
                "datafactory_http.retry.requests.get",
                return_value=mock_resp,
            ) as mock_get,
            patch("datafactory_http.retry.time.sleep") as mock_sleep,
            pytest.raises(requests.HTTPError),
        ):
            request_with_retry(
                "http://test", max_retries=3, timeout=5
            )

        assert mock_get.call_count == 1  # No retry
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
                "datafactory_http.retry.requests.get",
                side_effect=[fail_resp, ok_resp],
            ) as mock_get,
            patch("datafactory_http.retry.time.sleep"),
            patch(
                "datafactory_http.retry.random.uniform",
                return_value=0.0,
            ),
        ):
            request_with_retry(
                "http://test", max_retries=3, timeout=5
            )

        assert mock_get.call_count == 2  # Retried once


class TestRequestWithRetryRed:

    def test_timeout_exception_retried(self) -> None:
        """requests.Timeout is retried like other transient errors."""
        from datafactory_http import request_with_retry

        ok_resp = MagicMock()
        ok_resp.raise_for_status = MagicMock()

        with (
            patch(
                "datafactory_http.retry.requests.get",
                side_effect=[
                    requests.Timeout("timed out"),
                    ok_resp,
                ],
            ) as mock_get,
            patch("datafactory_http.retry.time.sleep") as mock_sleep,
            patch(
                "datafactory_http.retry.random.uniform",
                return_value=0.5,
            ),
        ):
            request_with_retry(
                "http://test", max_retries=3, timeout=5,
            )

        assert mock_get.call_count == 2
        assert mock_sleep.call_count == 1

    def test_http_error_with_no_response_retried(self) -> None:
        """HTTPError with response=None is retried (not treated as 4xx)."""
        from datafactory_http import request_with_retry

        ok_resp = MagicMock()
        ok_resp.raise_for_status = MagicMock()

        with (
            patch(
                "datafactory_http.retry.requests.get",
                side_effect=[
                    requests.HTTPError(response=None),
                    ok_resp,
                ],
            ) as mock_get,
            patch("datafactory_http.retry.time.sleep"),
            patch(
                "datafactory_http.retry.random.uniform",
                return_value=0.0,
            ),
        ):
            request_with_retry(
                "http://test", max_retries=3, timeout=5,
            )

        assert mock_get.call_count == 2
