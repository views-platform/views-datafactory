"""Falsification audit: development → main merge readiness.

Claim: "Development is ready to merge to main for Hetzner deployment."
Audit date: 2026-05-21.

F8: Two changed source files have no test coverage for the specific
    changed code path (hostname or "" fallback in netrc.authenticators).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch


class TestF8NetrcHostnameFallback:
    """F8: The `or ""` fallback for parsed.hostname must not break
    netrc lookup when hostname is None (e.g., file:// URL)."""

    def test_defaults_hostname_none_does_not_raise(self) -> None:
        """get_last_valid_month_id with a URL that has no hostname
        should not raise TypeError from netrc.authenticators(None)."""
        from datafactory_query.defaults import get_last_valid_month_id

        with patch("datafactory_query.defaults.urllib.request.urlopen") as mock_open:
            mock_resp = MagicMock()
            mock_resp.__enter__ = MagicMock(return_value=mock_resp)
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_resp.read.return_value = b'{"last_valid_month_id": 500}'
            mock_open.return_value = mock_resp

            result = get_last_valid_month_id(zarr_url="file:///tmp/test")
            assert result == 500

    def test_dataset_resolve_storage_with_netrc(self) -> None:
        """_resolve_storage_options for an HTTP URL exercises the
        netrc.authenticators(parsed.hostname or "") path."""
        from datafactory_query.dataset import _resolve_storage_options

        mock_nrc = MagicMock()
        mock_nrc.authenticators.return_value = ("user", "", "pass")
        mock_netrc_cls = MagicMock(return_value=mock_nrc)

        with patch.dict(
            "sys.modules",
            {},
        ), patch("netrc.netrc", mock_netrc_cls):
            opts = _resolve_storage_options("http://example.com/grid.zarr")

        mock_nrc.authenticators.assert_called_once_with("example.com")
        assert opts is not None
        assert "client_kwargs" in opts
        auth = opts["client_kwargs"]["auth"]
        assert auth.login == "user"
        assert auth.password == "pass"

    def test_dataset_resolve_storage_no_netrc(self) -> None:
        """_resolve_storage_options still returns valid options
        when .netrc is missing."""
        from datafactory_query.dataset import _resolve_storage_options

        with patch("netrc.netrc", side_effect=FileNotFoundError):
            opts = _resolve_storage_options("http://example.com/grid.zarr")

        assert opts is not None
        assert "client_kwargs" in opts
        assert "auth" not in opts["client_kwargs"]
