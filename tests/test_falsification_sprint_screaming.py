"""Falsification test stubs for sprint plan v1.2.21 screaming architecture audit.

Generated: 2026-05-24
Claim: Sprint plan corrects toward screaming architecture — files and
       folders clearly separated by responsibility, one concept per file,
       no dumping grounds.
Verdict: CONTESTED (1 soft falsification, 0 hard).

R-1 found that Task 3 step 1 directs VIEWS_EPOCH_YEAR into
digests_and_ledgers.py (a file about content digests and JSONL ledger
operations) as the primary option, with constants.py only as a
parenthetical alternative. A domain constant about calendar epochs
does not belong in a file named "digests and ledgers."
"""

from __future__ import annotations

import ast
from pathlib import Path


class TestR1ViewsEpochYearPlacement:
    """Task 3 adds VIEWS_EPOCH_YEAR to provenance. The plan's
    primary instruction places it in digests_and_ledgers.py, whose
    docstring is 'content digests and JSONL ledger operations.'

    VIEWS_EPOCH_YEAR (calendar epoch for month_id calculation) is
    a domain constant unrelated to digests or ledgers. Placing it
    in this file makes the file a dumping ground for unrelated
    constants.

    This test verifies that if VIEWS_EPOCH_YEAR exists in
    provenance, it lives in a file whose name reflects its purpose
    (e.g. constants.py, epoch.py) — not in digests_and_ledgers.py.
    """

    def test_views_epoch_year_not_in_digests_and_ledgers(self) -> None:
        dal = Path(
            "src/datafactory_provenance/digests_and_ledgers.py"
        )
        tree = ast.parse(dal.read_text())

        module_names: set[str] = set()
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        module_names.add(target.id)

        assert "VIEWS_EPOCH_YEAR" not in module_names, (
            "VIEWS_EPOCH_YEAR is a domain constant (calendar epoch "
            "for month_id calculation). It does not belong in "
            "digests_and_ledgers.py, which is about content digests "
            "and JSONL ledger operations. Move it to a dedicated "
            "constants.py or similar file within provenance."
        )
