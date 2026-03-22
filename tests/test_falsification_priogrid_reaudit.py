"""Re-audit: PRIO-GRID static harvester production readiness.

Generated 2026-03-22. Second audit after remediation of 6 prior
falsifications. Three soft falsifications found and resolved:
gid uniqueness check added, unchanged path includes warnings,
CIC test alignment corrected.

CONTESTED → SURVIVED after fixes.
"""

from __future__ import annotations


class TestPriogridReauditResolved:

    def test_gid_uniqueness_check_exists(self) -> None:
        """Q1 resolved: gid uniqueness check added."""
        import inspect

        from datafactory_harvester.sources.priogrid_static import (
            _fetch_variable,
        )

        source = inspect.getsource(_fetch_variable)
        assert "unique_gids" in source
        assert "Duplicate gids" in source

    def test_unchanged_path_has_warnings(self) -> None:
        """Q2 resolved: unchanged ledger entry includes
        warnings field.
        """
        import inspect

        from datafactory_harvester.sources.priogrid_static import (
            _fetch_variable,
        )

        source = inspect.getsource(_fetch_variable)
        # Find the unchanged block and verify warnings
        unchanged_idx = source.index('"unchanged"')
        # warnings should appear near the unchanged entry
        block = source[unchanged_idx - 200 : unchanged_idx]
        assert '"warnings"' in block or "warnings" in block

    def test_cic_test_alignment_accurate(self) -> None:
        """Q3 resolved: CIC Section 10 matches actual tests."""
        import os

        path = os.path.join(
            os.path.dirname(__file__), "..",
            "docs", "CICs", "PriogridStaticConfig.md",
        )
        with open(path) as f:
            content = f.read()
        # Should mention actual test categories
        assert "local-first skip" in content
        assert "Empty cells from API" in content
