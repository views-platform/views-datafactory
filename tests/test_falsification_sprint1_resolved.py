"""Falsification stubs: Sprint 1 concern resolution completeness.

Source: /falsify all concerns from sprint 1 have been resolved (2026-05-26)
Claim: All concerns C-203 through C-211 have been resolved.
Verdict: CONTESTED (0 hard, 2 soft).

F-1 (soft): test_parse_filter_failure_writes_ledger asserts outcome but
    not reason content — the production fix works (str(exc) confirmed
    here), but the existing test in test_vdem_harvester.py doesn't verify
    that the specific column name appears in the ledger reason field.
F-2 (soft): C-209, C-210, C-211 are resolved but orphaned from work
    packages — no sprint retrospective traceability.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestF1LedgerReasonSpecificity:
    """C-207 fix captures specific error — test must verify reason content."""

    def test_parse_filter_ledger_reason_contains_column_name(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_harvester.sources.vdem import (
            VdemConfig,
            fetch_vdem,
        )

        csv_missing_col = (
            "country_text_id,year,v2x_libdem\n"
            "NOR,2020,0.89\n"
        )
        import io
        import zipfile
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("V-Dem-CY-Full+Others-v16.csv", csv_missing_col)
        zip_data = buf.getvalue()

        mock_resp = MagicMock()
        mock_resp.content = zip_data

        config = VdemConfig(
            variables=("v2x_libdem", "v2xcl_dmove", "v2x_clphy"),
            data_dir=tmp_path / "raw",
            ledger_path=tmp_path / "ledger.jsonl",
        )

        with (
            patch(
                "datafactory_harvester.sources.vdem"
                ".request_with_retry",
                return_value=mock_resp,
            ),
            pytest.raises(ValueError),
        ):
            fetch_vdem(config)

        ledger = (tmp_path / "ledger.jsonl").read_text().strip()
        entry = json.loads(ledger.splitlines()[-1])
        assert entry["reason"] != "CSV column schema mismatch", (
            "Ledger reason is still the old hardcoded string — "
            "should contain the specific ValueError message "
            "with the missing column name(s)"
        )
        reason = entry["reason"].lower()
        assert "missing" in reason or "v2xcl_dmove" in reason, (
            f"Ledger reason {entry['reason']!r} does not mention "
            "the missing column — str(exc) may not propagate"
        )


class TestF2WorkPackageOrphans:
    """Resolved concerns should be traceable through work packages."""

    def test_c209_in_work_package(self) -> None:
        register = Path("reports/technical_risk_register.md").read_text()
        wp_section = register.split("## Work Packages")[1].split("## ")[0]
        assert "C-209" in wp_section, (
            "C-209 (ADR-009 drift) is resolved but not assigned "
            "to any work package — no sprint traceability"
        )

    def test_c210_in_work_package(self) -> None:
        register = Path("reports/technical_risk_register.md").read_text()
        wp_section = register.split("## Work Packages")[1].split("## ")[0]
        assert "C-210" in wp_section, (
            "C-210 (ADR-016 drift) is resolved but not assigned "
            "to any work package — no sprint traceability"
        )

    def test_c211_in_work_package(self) -> None:
        register = Path("reports/technical_risk_register.md").read_text()
        wp_section = register.split("## Work Packages")[1].split("## ")[0]
        assert "C-211" in wp_section, (
            "C-211 (consumer guide stale) is resolved but not "
            "assigned to any work package — no sprint traceability"
        )
