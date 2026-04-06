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
        archive = reports / "technical_risk_register_resolved.md"

        assert active.exists(), (
            "technical_risk_register.md not found"
        )
        assert archive.exists(), (
            "technical_risk_register_resolved.md not found"
        )

        active_text = active.read_text()
        archive_text = archive.read_text()

        # Count full entries (### C-xx or ### D-xx lines)
        entry_re = re.compile(r"^### [CD]-\d+", re.MULTILINE)
        n_active = len(entry_re.findall(active_text))
        n_archive = len(entry_re.findall(archive_text))

        # Count early reference table rows (| C-xx |)
        early_re = re.compile(
            r"^\| C-\d+", re.MULTILINE
        )
        n_early = len(early_re.findall(archive_text))

        n_resolved = n_archive + n_early
        # Subtract disagreements (D-xx) from archive count
        # — they are tracked separately in the header
        n_archive_disagreements = len(
            re.findall(
                r"^### D-\d+", archive_text, re.MULTILINE
            )
        )
        n_resolved_concerns = n_resolved - n_archive_disagreements

        # Verify header claims match structural counts
        assert f"{n_resolved_concerns} resolved" in active_text, (
            f"Header should say '{n_resolved_concerns} resolved' "
            f"but doesn't. Archive has {n_archive} full entries "
            f"({n_archive_disagreements} disagreements) + "
            f"{n_early} early reference rows."
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
