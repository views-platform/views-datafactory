"""Falsification stubs: Martin package principles compliance.

Source: /falsify audit 2026-05-27
Claim: "This project adheres to REP, CCP, CRP, ADP, SDP, SAP."
Verdict: CONTESTED (0 hard, 3 soft).

P-2 (soft): SAP violation — maximally stable packages
    (provenance I=0.00, http I=0.00, adapters I=0.00) have near-zero
    abstractness (A=0.07, 0.00, 0.00). All sit in the "zone of pain."
    Accepted under WET-before-DRY (C-44, threshold: 10 sources).
P-3 (soft): CRP violation — datafactory_provenance exports 21
    symbols but each consumer uses only 6-7, and different subsets.
    file_lock and last_digest_for_version are single-consumer symbols.
    Accepted under WET-before-DRY (C-44, threshold: 10 sources).
P-5 (soft): CCP violation — datafactory_priogrid mixes 3
    independent concern groups (spatial backbone, temporal backbone,
    shapefile I/O + parity) that change for different reasons.
    Accepted: single PRIO-GRID domain entity cohesion outweighs
    change-frequency separation at current scale.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest


class TestP2SapZoneOfPain:
    """Maximally stable packages should have sufficient abstractness
    to survive downstream change without forcing consumers to depend
    on concrete implementations."""

    @pytest.mark.xfail(
        reason=(
            "C-44: WET-before-DRY — 9 sources, threshold 10. "
            "Abstract types deferred until 10th source forces "
            "interface extraction."
        ),
        strict=True,
    )
    def test_provenance_abstractness_above_threshold(self) -> None:
        """provenance has I=0.00 (maximally stable) but A=0.07.
        SAP says stable packages should be abstract enough to
        extend without modification."""
        src = Path("src/datafactory_provenance")
        py_files = list(src.glob("*.py"))

        abstract_count = 0
        concrete_count = 0
        for py_file in py_files:
            if py_file.name == "__init__.py":
                continue
            tree = ast.parse(py_file.read_text())
            for node in ast.iter_child_nodes(tree):
                if isinstance(node, ast.ClassDef):
                    bases = [
                        getattr(b, "id", getattr(b, "attr", ""))
                        for b in node.bases
                    ]
                    is_abstract = (
                        "ABC" in bases
                        or "Protocol" in bases
                        or "Generic" in bases
                    )
                    if is_abstract:
                        abstract_count += 1
                    else:
                        concrete_count += 1

        total = abstract_count + concrete_count
        abstractness = abstract_count / total if total else 0.0
        assert abstractness >= 0.5, (
            f"provenance abstractness A={abstractness:.2f} "
            f"({abstract_count} abstract, {concrete_count} concrete). "
            f"SAP recommends A≥0.5 for packages at I=0.00 "
            f"to avoid the zone of pain."
        )


class TestP3CrpProvenanceBundling:
    """Consumers forced to depend on symbols they don't use
    creates unnecessary coupling and redeployment risk."""

    @pytest.mark.xfail(
        reason=(
            "C-44: WET-before-DRY — 9 sources, threshold 10. "
            "Provenance sub-packaging deferred until 10th source "
            "forces reuse-group separation."
        ),
        strict=True,
    )
    def test_all_consumers_use_majority_of_exports(self) -> None:
        """Each consumer of provenance should use >50% of the
        symbols it's forced to depend on. Currently consumers
        use 6-7 of 21 exports (~30%)."""
        mod = importlib.import_module("datafactory_provenance")
        exported = set(mod.__all__)

        src = Path("src")
        consumers = [
            "datafactory_compilation",
            "datafactory_consolidation",
            "datafactory_harvester",
            "datafactory_priogrid",
            "datafactory_viewpoint",
        ]
        threshold = 0.50

        violations: list[str] = []
        for consumer in consumers:
            consumer_dir = src / consumer
            if not consumer_dir.exists():
                continue
            consumer_text = ""
            for py_file in consumer_dir.rglob("*.py"):
                consumer_text += py_file.read_text()

            used = {
                sym
                for sym in exported
                if sym in consumer_text
            }
            ratio = len(used) / len(exported) if exported else 1.0
            if ratio < threshold:
                violations.append(
                    f"{consumer}: uses {len(used)}/{len(exported)} "
                    f"({ratio:.0%})"
                )

        assert not violations, (
            f"CRP: {len(violations)} consumers use <50% of "
            f"provenance exports:\n"
            + "\n".join(f"  {v}" for v in violations)
        )


class TestP5CcpPriogridConcernMixing:
    """Modules that change for different reasons should not live
    in the same package, because a change in one concern forces
    redeployment of the others."""

    @pytest.mark.xfail(
        reason=(
            "C-44: WET-before-DRY — priogrid mixes spatial, "
            "temporal, and shapefile I/O concerns in one package. "
            "Accepted: single domain entity (PRIO-GRID) provides "
            "sufficient cohesion at 9-source scale."
        ),
        strict=True,
    )
    def test_priogrid_concern_groups_independent(self) -> None:
        """priogrid has 3 concern groups that change independently:
        spatial (cell_generator, grid_config, land_mask),
        temporal (temporal_config, temporal_generator),
        shapefile (shapefile_harvester, shapefile_reader,
        parity_validation)."""
        spatial = {
            "cell_generator.py",
            "grid_config.py",
            "land_mask.py",
        }
        temporal = {
            "temporal_config.py",
            "temporal_generator.py",
        }
        shapefile = {
            "shapefile_harvester.py",
            "shapefile_reader.py",
            "parity_validation.py",
        }

        pkg = Path("src/datafactory_priogrid")
        modules = {
            f.name
            for f in pkg.glob("*.py")
            if f.name not in ("__init__.py",)
            and not f.name.startswith("_")
        }

        classified = spatial | temporal | shapefile
        bridging = {"spatiotemporal.py"}
        unclassified = modules - classified - bridging

        concern_groups = [
            g for g in [spatial, temporal, shapefile] if g
        ]
        assert len(concern_groups) <= 1, (
            f"priogrid has {len(concern_groups)} independent "
            f"concern groups in one package: "
            f"spatial={spatial & modules}, "
            f"temporal={temporal & modules}, "
            f"shapefile={shapefile & modules}. "
            f"CCP says things that change together should live "
            f"together — these change independently."
            + (
                f"\nUnclassified modules: {unclassified}"
                if unclassified
                else ""
            )
        )
