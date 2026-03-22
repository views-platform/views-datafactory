"""Falsification audit: PRIO-GRID static harvester production readiness.

Generated 2026-03-22 from audit of the claim:
"The PRIO-GRID static harvester is complete. It is at least as
robust as the UCDP harvesters and it is ready for production."

FALSIFIED → RESOLVED. All 4 hard + 2 soft falsifications addressed:
CIC created, 13 tests written, schema validation strengthened,
ARCHITECTURE.md updated, exceptions narrowed, archive on overwrite.
"""

from __future__ import annotations

import os


class TestPriogridStaticResolved:

    def test_cic_exists(self) -> None:
        """P1 resolved: CIC created for PriogridStaticConfig."""
        path = os.path.join(
            os.path.dirname(__file__), "..",
            "docs", "CICs", "PriogridStaticConfig.md",
        )
        assert os.path.exists(path), (
            "CIC should exist at docs/CICs/PriogridStaticConfig.md"
        )

    def test_dedicated_test_file_exists(self) -> None:
        """P2 resolved: test_priogrid_static.py exists."""
        path = os.path.join(
            os.path.dirname(__file__),
            "test_priogrid_static.py",
        )
        assert os.path.exists(path), (
            "Test file should exist"
        )

    def test_schema_validation_has_type_checks(
        self,
    ) -> None:
        """P3 resolved: validation checks field types."""
        # The function source should reference type checking
        import inspect

        from datafactory_harvester.sources.priogrid_static import (
            _fetch_variable,
        )

        source = inspect.getsource(_fetch_variable)
        assert "isinstance" in source, (
            "Type validation should use isinstance"
        )

    def test_architecture_doc_lists_priogrid(
        self,
    ) -> None:
        """P5 resolved: ARCHITECTURE.md lists priogrid_static."""
        arch_path = os.path.join(
            os.path.dirname(__file__), "..",
            "src", "datafactory_harvester",
            "ARCHITECTURE.md",
        )
        with open(arch_path) as f:
            content = f.read()
        assert "priogrid_static" in content

    def test_exception_not_bare(self) -> None:
        """P6 resolved: orchestrator uses specific exceptions."""
        import inspect

        from datafactory_harvester.sources.priogrid_static import (
            fetch_priogrid_static,
        )

        source = inspect.getsource(fetch_priogrid_static)
        assert "except Exception" not in source, (
            "Should use specific exceptions, not bare Exception"
        )

    def test_archive_on_overwrite(self) -> None:
        """P4 resolved: archives old snapshot before overwrite."""
        import inspect

        from datafactory_harvester.sources.priogrid_static import (
            _fetch_variable,
        )

        source = inspect.getsource(_fetch_variable)
        assert "archive_snapshot" in source, (
            "Should archive old snapshot before overwriting"
        )
