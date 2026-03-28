"""Tests for datafactory_http.request_with_retry."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestRequestWithRetryGreen:

    def test_retries_on_failure(self) -> None:
        """Retry with exponential backoff on transient errors."""
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
        mock_sleep.assert_any_call(1)  # 2^0
        mock_sleep.assert_any_call(2)  # 2^1

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
