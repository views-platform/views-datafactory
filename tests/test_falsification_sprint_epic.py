"""Falsification stubs: Sprint epic #205 readiness.

Source: /falsify "we're 100% ready to execute the Sprint epic" (2026-06-17)

Hard falsifications:
  F1 — Branch not pushed to origin (local-only commit)
  F3 — Issue #196 describes wrong input types (pa.Table vs list[dict])
  F8 — Risk register header says 224 resolved but test counts 226

Soft falsifications:
  F6 — Issue #200 (ADR) has no concrete ADR number
  F7 — Issue #200 missing unexpected-behavior protocol
  F8b — test_falsification_deploy_v130 lacks conditional xfail
"""

from __future__ import annotations

import subprocess


class TestF1BranchPushed:
    """Sprint branch must be pushed to origin before execution begins."""

    def test_branch_has_remote_tracking(self) -> None:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref",
             "feature/sprint-characterization-tests@{upstream}"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, (
            "feature/sprint-characterization-tests has no upstream — "
            "push before starting sprint work"
        )


class TestF3EventValidationInputTypes:
    """Issue #196 test fixtures must use list[dict], not pa.Table."""

    def test_validate_events_takes_list_of_dicts(self) -> None:
        import inspect

        from datafactory_harvester.event_validation import validate_events

        sig = inspect.signature(validate_events)
        events_param = sig.parameters["events"]
        assert "list" in str(events_param.annotation).lower(), (
            f"validate_events 'events' parameter is {events_param.annotation}, "
            f"not list[dict] — issue #196 fixtures must match"
        )

    def test_compare_snapshots_new_events_takes_list_of_dicts(self) -> None:
        import inspect

        from datafactory_harvester.event_validation import compare_snapshots

        sig = inspect.signature(compare_snapshots)
        new_events_param = sig.parameters["new_events"]
        assert "list" in str(new_events_param.annotation).lower(), (
            f"compare_snapshots 'new_events' parameter is "
            f"{new_events_param.annotation}, not list[dict] — "
            f"issue #196 says pa.Table but actual API takes list[dict]"
        )


class TestF6AdrNumberAssigned:
    """Issue #200 must specify a concrete ADR number, not 0XX."""

    def test_adr_045_exists(self) -> None:
        from pathlib import Path

        adr = Path("docs/ADRs/045_data_soundness_invariants.md")
        assert adr.exists(), "ADR-045 not found — issue #200 requires it"


class TestF8RegisterHeaderAccuracy:
    """Risk register header counts must match actual resolved entries."""

    def test_header_resolved_count_matches_actual(self) -> None:
        import re
        from pathlib import Path

        active = Path("reports/technical_risk_register.md").read_text()
        header_match = re.search(r":\s*(\d+) resolved,", active)
        assert header_match, "No 'N resolved' in register header"
        header_count = int(header_match.group(1))

        archive_path = Path(
            "reports/archive/technical_risk_register_resolved.md"
        )
        archive = archive_path.read_text() if archive_path.exists() else ""

        resolved_ids: set[str] = set()
        resolved_ids.update(
            re.findall(r"^### (C-\d+)", archive, re.MULTILINE)
        )
        resolved_ids.update(
            re.findall(r"^\| (C-\d+)", archive, re.MULTILINE)
        )
        resolved_ids.update(
            re.findall(r"^### ~~(C-\d+)", active, re.MULTILINE)
        )
        resolved_ids.update(
            re.findall(r"^\| ~~(C-\d+)~~", active, re.MULTILINE)
        )

        assert header_count == len(resolved_ids), (
            f"Header says '{header_count} resolved' but found "
            f"{len(resolved_ids)} unique resolved C-IDs"
        )
