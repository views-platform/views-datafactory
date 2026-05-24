"""Falsification test stubs for sprint plan v1.2.21 package principles audit.

Generated: 2026-05-24
Claim: Sprint plan corrects toward REP, CCP, CRP, ADP, SDP, SAP.
Verdict: CONTESTED (1 soft falsification, 0 hard).

P-6 found that datafactory_provenance sits in the SAP Zone of Pain:
Instability I=0.00, Abstractness A=0.00, Distance D=1.00.
The plan adds VIEWS_EPOCH_YEAR (Task 3) without adding any abstraction,
pushing the package further into the zone.
"""

from __future__ import annotations

import ast
from pathlib import Path


class TestP6ProvenanceAbstractness:
    """datafactory_provenance has 5 modules, 0 abstract classes,
    0 Protocol definitions. Stability I=0.00 (no outbound imports),
    Abstractness A=0.00. Distance from Main Sequence D=1.00.

    Martin's SAP says stable packages should be abstract enough to
    survive change. A package with D=1.00 is maximally in the
    Zone of Pain — concrete and hard to change despite being
    depended on by everything.

    This test checks that provenance has at least one Protocol or
    ABC, which would move A > 0 and reduce D.
    """

    def test_provenance_has_at_least_one_abstraction(self) -> None:
        prov_dir = Path("src/datafactory_provenance")
        py_files = list(prov_dir.glob("*.py"))
        assert py_files, "No Python files found in provenance package"

        abstractions: list[str] = []
        for py_file in py_files:
            tree = ast.parse(py_file.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    for base in node.bases:
                        base_name = ""
                        if isinstance(base, ast.Name):
                            base_name = base.id
                        elif isinstance(base, ast.Attribute):
                            base_name = base.attr
                        if base_name in ("ABC", "Protocol"):
                            abstractions.append(
                                f"{py_file.name}:{node.name}"
                            )

        assert abstractions, (
            "datafactory_provenance has 0 abstract classes or Protocols "
            f"across {len(py_files)} modules. "
            "Stability I=0.00, Abstractness A=0.00, Distance D=1.00 "
            "(Zone of Pain). Add at least one Protocol to define the "
            "contract that consumers depend on, moving A > 0."
        )
