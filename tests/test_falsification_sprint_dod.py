"""Falsification test stubs for sprint plan v1.2.21 Definition of Done audit.

Generated: 2026-05-24
Claim: Sprint plan has a clear and verifiable Definition of Done.
Verdict: CONTESTED (3 soft falsifications, 0 hard).

D-1: Task 1 has no '### Acceptance criteria' section (all other tasks do).
     Also contains two contradictory header blocks (64 vs 65 open).
D-2: Three acceptance criteria require human judgment instead of binary
     pass/fail: "matches actual contents", "~120-150 lines", "a developer
     can find."
D-5: No terminal action defined. Plan never says "merge to development"
     or "create PR" — a developer finishing all tasks wouldn't know the
     final step.
"""

from __future__ import annotations

import re
from pathlib import Path

PLAN_PATH = Path(
    "reports/sprint_plan_maintenance_v1221.md"
)


class TestD1Task1AcceptanceCriteria:
    """Every task except Task 1 has a '### Acceptance criteria'
    section. Task 1 has '### Verification' and '### Final header'
    but these are non-standard section names. A developer scanning
    for acceptance criteria would miss Task 1.
    """

    def test_every_task_has_acceptance_criteria_section(self) -> None:
        text = PLAN_PATH.read_text()
        task_headers = re.findall(
            r"^## Task \d+:.*$", text, re.MULTILINE,
        )
        ac_sections = re.findall(
            r"^### Acceptance criteria", text, re.MULTILINE,
        )
        assert len(ac_sections) >= len(task_headers), (
            f"Found {len(task_headers)} tasks but only "
            f"{len(ac_sections)} '### Acceptance criteria' sections. "
            f"Every task must have a formal acceptance criteria block."
        )

    def test_task1_no_contradictory_header_blocks(self) -> None:
        text = PLAN_PATH.read_text()
        task1_start = text.index("## Task 1:")
        task2_start = text.index("## Task 2:")
        task1_text = text[task1_start:task2_start]
        code_blocks = re.findall(
            r"```\n(.*?)```", task1_text, re.DOTALL,
        )
        header_blocks = [
            b for b in code_blocks
            if "open concerns" in b
        ]
        assert len(header_blocks) <= 1, (
            f"Task 1 contains {len(header_blocks)} header blocks "
            f"with 'open concerns'. Only the corrected version "
            f"should remain — the wrong one must be removed."
        )


class TestD2SubjectiveAcceptanceCriteria:
    """Three acceptance criteria use subjective language that
    requires human judgment rather than a binary command check:
    - Task 3: 'ADR-012 description matches provenance actual contents'
    - Task 8: 'line count reduced by ~120-150 lines'
    - Task 10: 'A developer can find the relevant test'
    """

    def test_no_tilde_ranges_in_acceptance_criteria(self) -> None:
        text = PLAN_PATH.read_text()
        ac_blocks: list[str] = []
        in_ac = False
        for line in text.splitlines():
            if line.strip() == "### Acceptance criteria":
                in_ac = True
                continue
            if in_ac and line.startswith("### "):
                in_ac = False
            if in_ac:
                ac_blocks.append(line)

        ac_text = "\n".join(ac_blocks)
        tilde_ranges = re.findall(r"~\d+-\d+", ac_text)
        assert not tilde_ranges, (
            f"Acceptance criteria contain approximate ranges: "
            f"{tilde_ranges}. Acceptance criteria must be binary "
            f"(pass/fail), not approximate. Replace with a minimum "
            f"threshold (e.g. 'reduced by at least 100 lines')."
        )


class TestD5TerminalAction:
    """The plan defines a branch (chore/maintenance-v1221) and
    Final Verification steps, but never specifies the terminal
    action: merge to development, create PR, or ship.

    A developer completing all tasks and Final Verification would
    not know the final step.
    """

    def test_plan_defines_terminal_action(self) -> None:
        text = PLAN_PATH.read_text()
        final_section = text[text.index("## Final Verification"):]
        has_merge = "merge" in final_section.lower()
        has_pr = (
            "pull request" in final_section.lower()
            or "pr " in final_section.lower()
            or "gh pr" in final_section.lower()
        )
        has_ship = "ship" in final_section.lower()
        assert has_merge or has_pr or has_ship, (
            "Plan has no terminal action after Final Verification. "
            "It should specify: merge to development, create PR, "
            "or equivalent ship gate. Without this, the Definition "
            "of Done is incomplete."
        )
