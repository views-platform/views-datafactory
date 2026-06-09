"""Falsification stubs — issue closure audit (2026-06-09).

These tests encode soft falsifications found when verifying that
9 GitHub issues are "100% solved in code." All three were addressed
in the same session.

Source: /falsify "these issues are actually solved in code 100%"
"""

from __future__ import annotations

from pathlib import Path


class TestP2ExtensivePrefixCouplingComment:
    """#130 requires a code comment on _EXTENSIVE_PREFIXES noting
    that the prefix list must be extended for future count sources."""

    def test_coupling_comment_exists(self) -> None:
        src = Path("src/datafactory_adapters/_conservation.py").read_text()
        lines = src.splitlines()
        prefix_line = next(
            (
                i for i, line in enumerate(lines)
                if "_EXTENSIVE_PREFIXES" in line
            ),
            None,
        )
        assert prefix_line is not None, "_EXTENSIVE_PREFIXES not found"
        context = "\n".join(
            lines[max(0, prefix_line - 2) : prefix_line + 3]
        )
        assert any(
            kw in context.lower()
            for kw in ("extend", "wdi", "future", "coupling", "add")
        ), (
            "Issue #130 requires a comment near _EXTENSIVE_PREFIXES "
            "noting the list must be extended for new count sources."
        )


class TestP7DefaultRemoteExport:
    """#16 centralizes the Hetzner IP. The issue specified
    DEFAULT_ZARR_URL; the implementation exports DEFAULT_REMOTE
    (a RemoteConfig dataclass) — better design, same function."""

    def test_default_remote_importable(self) -> None:
        from datafactory_query import DEFAULT_REMOTE

        assert hasattr(DEFAULT_REMOTE, "server")
        assert hasattr(DEFAULT_REMOTE, "zarr_url")
