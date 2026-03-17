"""ADR-002 import enforcement: verify the dependency DAG.

The topology rules (docs/ADRs/002_topology_and_dependency_rules.md):
- datafactory_core imports nothing from datafactory_*
- datafactory_grid imports only from datafactory_core
- datafactory_harvester imports only from datafactory_core
- datafactory_synthetic imports only from datafactory_core
- datafactory_compiler imports only from datafactory_core and datafactory_grid
"""

from __future__ import annotations

import ast
from pathlib import Path

# Allowed imports per package (beyond stdlib and external libs)
ALLOWED_INTERNAL_IMPORTS: dict[str, set[str]] = {
    "datafactory_core": set(),
    "datafactory_grid": {"datafactory_core"},
    "datafactory_harvester": {"datafactory_core"},
    "datafactory_synthetic": {"datafactory_core"},
    "datafactory_compiler": {"datafactory_core", "datafactory_grid"},
}

ALL_PACKAGES = set(ALLOWED_INTERNAL_IMPORTS.keys())

SRC_DIR = Path(__file__).resolve().parent.parent / "src"


def _collect_imports(filepath: Path) -> list[str]:
    """Extract all imported module names from a Python file."""
    try:
        tree = ast.parse(filepath.read_text())
    except SyntaxError:
        return []

    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.append(node.module.split(".")[0])
    return imports


def test_no_forbidden_internal_imports() -> None:
    """Every datafactory_* package respects its allowed import set."""
    violations: list[str] = []

    for package_name, allowed in ALLOWED_INTERNAL_IMPORTS.items():
        package_dir = SRC_DIR / package_name
        if not package_dir.exists():
            continue

        forbidden = ALL_PACKAGES - allowed - {package_name}

        for py_file in package_dir.rglob("*.py"):
            imported = _collect_imports(py_file)
            for mod in imported:
                if mod in forbidden:
                    rel = py_file.relative_to(SRC_DIR)
                    violations.append(
                        f"{rel} imports {mod} "
                        f"(allowed for {package_name}: {sorted(allowed) or 'none'})"
                    )

    assert violations == [], (
        "ADR-002 topology violations:\n" + "\n".join(f"  - {v}" for v in violations)
    )
