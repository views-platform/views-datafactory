"""Falsification stubs — issue closure audit (2026-06-09).

These tests encode soft falsifications found when verifying that
9 GitHub issues are "100% solved in code." All three were addressed
in the same session.

Source: /falsify "these issues are actually solved in code 100%"
"""

from __future__ import annotations


class TestP7DefaultRemoteExport:
    """#16 centralizes the Hetzner IP. The issue specified
    DEFAULT_ZARR_URL; the implementation exports DEFAULT_REMOTE
    (a RemoteConfig dataclass) — better design, same function."""

    def test_default_remote_importable(self) -> None:
        from datafactory_query import DEFAULT_REMOTE

        assert hasattr(DEFAULT_REMOTE, "server")
        assert hasattr(DEFAULT_REMOTE, "zarr_url")
