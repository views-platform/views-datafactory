"""ADR-012 import enforcement: verify the dependency DAG.

The topology rules (docs/ADRs/012_four_layer_data_architecture.md):
- datafactory_provenance imports nothing from datafactory_*
- datafactory_priogrid imports only from datafactory_provenance
- datafactory_harvester imports only from datafactory_provenance
- datafactory_consolidation imports only from datafactory_provenance
- datafactory_viewpoint imports only from datafactory_provenance
- datafactory_compilation imports from datafactory_provenance + datafactory_priogrid
"""

from __future__ import annotations

import ast
from pathlib import Path

# Allowed imports per package (beyond stdlib and external libs)
ALLOWED_INTERNAL_IMPORTS: dict[str, set[str]] = {
    "datafactory_provenance": set(),
    "datafactory_http": set(),
    "datafactory_priogrid": {"datafactory_provenance", "datafactory_http"},
    "datafactory_harvester": {"datafactory_provenance", "datafactory_http"},
    "datafactory_consolidation": {"datafactory_provenance"},
    "datafactory_viewpoint": {"datafactory_provenance"},
    "datafactory_compilation": {"datafactory_provenance", "datafactory_priogrid"},
    "datafactory_adapters": set(),  # No datafactory_* imports — extractable
    "datafactory_query": {"datafactory_priogrid", "datafactory_adapters"},
}

ALL_PACKAGES = set(ALLOWED_INTERNAL_IMPORTS.keys())

SRC_DIR = Path(__file__).resolve().parent.parent / "src"


def _collect_imports(filepath: Path) -> tuple[list[str], str | None]:
    """Extract all imported module names from a Python file.

    Returns:
        Tuple of (import names, error message or None).
    """
    try:
        tree = ast.parse(filepath.read_text())
    except SyntaxError as exc:
        return [], f"SyntaxError: {exc}"

    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.append(node.module.split(".")[0])
    return imports, None


def test_no_forbidden_internal_imports() -> None:
    """Every datafactory_* package respects its allowed import set."""
    violations: list[str] = []

    for package_name, allowed in ALLOWED_INTERNAL_IMPORTS.items():
        package_dir = SRC_DIR / package_name
        if not package_dir.exists():
            continue

        forbidden = ALL_PACKAGES - allowed - {package_name}

        for py_file in package_dir.rglob("*.py"):
            imported, parse_error = _collect_imports(py_file)
            if parse_error is not None:
                rel = py_file.relative_to(SRC_DIR)
                violations.append(f"{rel} could not be parsed: {parse_error}")
                continue
            for mod in imported:
                if mod in forbidden:
                    rel = py_file.relative_to(SRC_DIR)
                    violations.append(
                        f"{rel} imports {mod} "
                        f"(allowed for {package_name}: {sorted(allowed) or 'none'})"
                    )

    assert violations == [], (
        "ADR-012 topology violations:\n" + "\n".join(f"  - {v}" for v in violations)
    )

def test_the_declared_graph_is_acyclic() -> None:
    """ADR-012 calls the layers "independent nodes in a DAG". Check that.

    The test above verifies the CODE conforms to ALLOWED_INTERNAL_IMPORTS.
    Nothing verified that the dict itself encodes a DAG — so adding
    ``"datafactory_provenance": {"datafactory_query"}`` would keep the suite
    green while declaring a cycle, and the guard would endorse it.

    That is C-350's shape: an assertion about conformance standing in for an
    assertion about the property. Cheap to close, so closed (#457).
    """
    for package in ALLOWED_INTERNAL_IMPORTS:
        seen: set[str] = set()
        stack = list(ALLOWED_INTERNAL_IMPORTS[package])
        while stack:
            node = stack.pop()
            assert node != package, (
                f"{package} reaches itself through the allow-list — the "
                f"declared graph contains a cycle. ADR-012's DAG is the "
                f"architecture; a cycle here means the guard below would "
                f"happily enforce a circular import topology."
            )
            if node not in seen:
                seen.add(node)
                stack.extend(ALLOWED_INTERNAL_IMPORTS.get(node, ()))


def test_every_package_on_disk_is_declared() -> None:
    """A package missing from the dict is silently EXEMPT, not an error.

    ``test_no_forbidden_internal_imports`` iterates the dict, not the
    filesystem, so a tenth ``src/datafactory_*`` package that nobody adds
    here is never checked at all. Absence currently means "unconstrained"
    when it should mean "you forgot" (#457).
    """
    on_disk = {
        p.name
        for p in SRC_DIR.iterdir()
        if p.is_dir() and p.name.startswith("datafactory_")
    }
    assert on_disk == set(ALLOWED_INTERNAL_IMPORTS), (
        f"src/ and ALLOWED_INTERNAL_IMPORTS disagree. "
        f"On disk but undeclared (and therefore UNGUARDED): "
        f"{sorted(on_disk - set(ALLOWED_INTERNAL_IMPORTS))}. "
        f"Declared but absent from disk: "
        f"{sorted(set(ALLOWED_INTERNAL_IMPORTS) - on_disk)}. "
        f"Add the package to the dict with its allowed imports — an empty "
        f"set if it may import no other datafactory_* package."
    )
