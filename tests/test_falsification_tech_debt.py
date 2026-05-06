"""Falsification audit: tech debt cleanup completeness.

Generated 2026-03-22 from audit of the claim:
"All tech debt apart from the two deferred items (C-06, C-07)
have been identified and handled."

CONTESTED → SURVIVED after fixes. Three soft falsifications
found and resolved: error message hardcoded shape constant,
concerns00.md header was stale, maturity test skip was outdated.
"""

from __future__ import annotations


class TestTechDebtResolved:

    def test_smoke_test_retired(self) -> None:
        """Resolved: smoke_test.py retired. Its functionality
        is covered by layer scripts and 376 tests.
        """
        from pathlib import Path

        smoke_test = (
            Path(__file__).parent.parent
            / "scripts"
            / "smoke_test.py"
        )
        assert not smoke_test.exists(), (
            "smoke_test.py should have been deleted"
        )

    def test_concerns_header_accuracy(self) -> None:
        """Resolved: concerns file renamed to
        technical_risk_register.md and split into
        active + resolved archive (ADR-020).

        Structural: counts actual entries in both files and
        compares to the header's claimed numbers, so the test
        breaks if entries are added/removed without updating
        the header.
        """
        import re
        from pathlib import Path

        old_file = (
            Path(__file__).parent.parent
            / "reports"
            / "concerns00.md"
        )
        assert not old_file.exists(), (
            "concerns00.md should be replaced by "
            "technical_risk_register.md"
        )

        reports = Path(__file__).parent.parent / "reports"
        active = reports / "technical_risk_register.md"
        archive = reports / "archive" / "technical_risk_register_resolved.md"

        assert active.exists(), (
            "technical_risk_register.md not found"
        )
        assert archive.exists(), (
            "technical_risk_register_resolved.md not found"
        )

        active_text = active.read_text()
        archive_text = archive.read_text()

        # Count full entries in active register
        entry_re = re.compile(r"^### [CD]-\d+", re.MULTILINE)
        n_active = len(entry_re.findall(active_text))

        # Collect unique resolved C-IDs from all sources:
        # 1. Archive full entries (### C-xx)
        # 2. Archive early reference rows (| C-xx)
        # 3. Active struck-through entries (### ~~C-xx~~)
        resolved_ids: set[str] = set()
        resolved_ids.update(
            re.findall(r"^### (C-\d+)", archive_text, re.MULTILINE)
        )
        resolved_ids.update(
            re.findall(r"^\| (C-\d+)", archive_text, re.MULTILINE)
        )
        resolved_ids.update(
            re.findall(r"^### ~~(C-\d+)", active_text, re.MULTILINE)
        )
        n_resolved_concerns = len(resolved_ids)

        # Verify header claims match structural counts
        assert f"{n_resolved_concerns} resolved" in active_text, (
            f"Header should say '{n_resolved_concerns} resolved' "
            f"but doesn't. Found {n_resolved_concerns} unique "
            f"resolved C-IDs across archive + active."
        )

        # Summary table should match full entry count
        summary_re = re.compile(
            r"^\| C-\d+", re.MULTILINE
        )
        n_summary = len(summary_re.findall(active_text))
        assert n_summary == n_active, (
            f"Summary table has {n_summary} rows but "
            f"active file has {n_active} full entries. "
            f"These must match 1:1."
        )

    def test_maturity_skip_reason_current(self) -> None:
        """Resolved: maturity test for .9 in smoke test
        converted from stale skip to passing assertion.
        """
        from pathlib import Path

        maturity_test = (
            Path(__file__).parent
            / "test_falsification_maturity.py"
        )
        content = maturity_test.read_text()
        # Should not have the stale skip reason
        assert "has zero .9 references" not in content
