"""Falsification test stubs for sprint plan v1.2.21 ADR alignment audit.

Generated: 2026-05-24
Claim: Sprint plan aligns 100% with ADRs and project philosophy.
Verdict: CONTESTED (3 soft falsifications, 0 hard).

Each stub documents a specific finding. Convert to real tests
when the corresponding fix is implemented.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# ── F-1: Provenance scope drift ──


class TestF1ProvenanceScopeDrift:
    """ADR-012 describes provenance as 'content digests and JSONL ledger
    operations.' In practice it also contains PIPELINE_SOURCES, SourceEntry,
    FRESHNESS_SLO_HOURS, validate_preflight(), and (after Task 3)
    VIEWS_EPOCH_YEAR.

    If VIEWS_EPOCH_YEAR is added to provenance, ADR-012 should be updated
    to acknowledge provenance's actual role as the foundation layer.
    """

    def test_adr_012_describes_provenance_actual_contents(self) -> None:
        adr_path = Path(
            "docs/ADRs/012_four_layer_data_architecture.md"
        )
        text = adr_path.read_text()
        assert "source_registry" in text.lower() or "foundation" in text.lower(), (
            "ADR-012 does not mention source_registry or foundation role. "
            "Provenance scope has drifted beyond 'digests and ledger operations' "
            "without ADR acknowledgement."
        )


# ── F-2: Extracted modules lack direct tests ──


class TestF2ExtractedModuleTestCoverage:
    """ADR-005 mandates test coverage for all non-trivial functionality.
    Extracted shared modules should have at minimum one direct test that
    exercises the function without going through the builder integration
    tests — so a developer modifying raster_io.py or temporal.py knows
    which test to run.
    """

    @pytest.mark.parametrize(
        "module_path",
        [
            "src/datafactory_viewpoint/raster_io.py",
            "src/datafactory_viewpoint/temporal.py",
            "src/datafactory_consolidation/tagging.py",
            "src/datafactory_compilation/output.py",
        ],
    )
    def test_extracted_module_has_direct_test(
        self, module_path: str,
    ) -> None:
        module_name = Path(module_path).stem
        test_dir = Path("tests")
        matching = list(test_dir.glob(f"test_{module_name}*.py"))
        assert matching, (
            f"No direct test file found for extracted module {module_path}. "
            f"ADR-005 requires coverage for non-trivial functionality. "
            f"Expected tests/test_{module_name}.py or similar."
        )


# ── F-7: ADR-012 references deleted synthetic module ──


class TestF7Adr012SyntheticReferences:
    """Task 9 deletes datafactory_synthetic. ADR-012 references it
    4 times (DAG diagram, import table, narrative, data flow).
    Six other ADRs also reference it. Deleting the module without
    updating these ADRs creates documentation drift.
    """

    def test_adr_012_no_stale_synthetic_reference(self) -> None:
        adr_path = Path(
            "docs/ADRs/012_four_layer_data_architecture.md"
        )
        if not Path("src/datafactory_synthetic").exists():
            text = adr_path.read_text()
            assert "datafactory_synthetic" not in text, (
                "ADR-012 still references datafactory_synthetic "
                "but the module has been deleted. "
                "Update the ADR to remove stale references."
            )

    @pytest.mark.parametrize(
        "adr_file",
        [
            "001_ontology_of_the_repository.md",
            "002_topology_and_dependency_rules.md",
            "005_testing_as_mandatory_critical_infrastructure.md",
            "009_boundary_contracts_and_configuration_validation.md",
        ],
    )
    def test_other_adrs_no_stale_synthetic_reference(
        self, adr_file: str,
    ) -> None:
        adr_path = Path("docs/ADRs") / adr_file
        if not Path("src/datafactory_synthetic").exists():
            text = adr_path.read_text()
            lines_with_ref = [
                i + 1
                for i, line in enumerate(text.splitlines())
                if "datafactory_synthetic" in line
            ]
            assert not lines_with_ref, (
                f"{adr_file} references datafactory_synthetic "
                f"on line(s) {lines_with_ref} but the module "
                f"has been deleted."
            )
