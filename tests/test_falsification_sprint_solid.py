"""Falsification test stubs for sprint plan v1.2.21 SOLID alignment audit.

Generated: 2026-05-24
Claim: Sprint plan corrects toward SOLID principles.
Verdict: CONTESTED (1 hard falsification, 0 soft).

S-4 found a correctness bug in Task 8: _load_source_grid references
DEFAULT_GRID_CONFIG and np which are imported inside main(), not at
module level. The function is defined before main() and would raise
NameError at runtime.
"""

from __future__ import annotations

import ast
from pathlib import Path


class TestS4LoadSourceGridScope:
    """Task 8 defines _load_source_grid before main() in
    assemble_grid.py, but the function references DEFAULT_GRID_CONFIG
    and np which are imported inside main() (lines 219, 222).

    This test verifies that all names used by _load_source_grid are
    available at the scope where the function is defined.
    """

    def test_load_source_grid_names_in_module_scope(self) -> None:
        script = Path("scripts/assemble_grid.py")
        source = script.read_text()
        tree = ast.parse(source)

        module_level_names: set[str] = set()
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_level_names.add(
                        alias.asname or alias.name.split(".")[0]
                    )
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    module_level_names.add(alias.asname or alias.name)
            elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                module_level_names.add(node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        module_level_names.add(target.id)

        required_by_helper = {"np", "json", "DEFAULT_GRID_CONFIG"}
        missing = required_by_helper - module_level_names
        assert not missing, (
            f"_load_source_grid (defined before main()) references "
            f"names not available at module scope: {missing}. "
            f"These are imported inside main(). Either move imports "
            f"to module level or pass as parameters."
        )
