"""Falsification tests — ADR-043 Azores supplement completeness.

Produced by a falsification audit (2026-06-12) of the claim:
"the missing-cells/unclaimed-cell issue in views-datafactory is now solved."

These tests FAIL BY DESIGN until the findings are fixed. Each test documents
one finding; see the audit report in views-postprocessing for full context.

The contract under test: land_gaul exists so that "consumers requiring complete
GAUL metadata use a clean cell set without maintaining exclusion lists"
(commit bac163e, issue #159). ADR-043's supplement broke that guarantee for
its own 6 recovered cells.
"""

import json
from pathlib import Path

import pyarrow.parquet as pq
import pytest

_GAUL_DIR = Path("data/raw/gaul_admin")
_QUERY_DIR = Path("src/datafactory_query")
_CLASSIFICATION = Path(
    "reports/investigation_gaul_excluded_cells/excluded_cell_classification.json"
)
_GAUL_AVAILABLE = (_GAUL_DIR / "gaul0_code.parquet").exists()
_SKIP_REASON = "GAUL parquet files not available — data/ is gitignored"


def _load(name: str) -> dict:
    t = pq.read_table(_GAUL_DIR / f"{name}.parquet")
    return dict(zip(
        t.column("gid").to_pylist(),
        t.column("value").to_pylist(),
        strict=True,
    ))


def _land_gaul() -> set[int]:
    return set(json.loads((_QUERY_DIR / "land_gaul_pgids.json").read_text()))


@pytest.mark.skipif(not _GAUL_AVAILABLE, reason=_SKIP_REASON)
class TestLandGaulCompletenessContract:
    """P2 (HARD): every land_gaul cell must carry complete GAUL metadata.

    Currently fails: the 6 ADR-043 supplemented cells (Azores) have
    gaul2_code = -1 while being land_gaul members. Downstream, the
    views-postprocessing lookup either drops them (delivery crash at
    validation: cells in-region but unenrichable) or ships -1 admin2
    codes to FAO. Region membership keys on gaul0_code only; the
    completeness guarantee must hold across all levels.
    """

    def test_land_gaul_cells_have_valid_gaul2_code(self):
        gaul2 = _load("gaul2_code")
        bad = [g for g in _land_gaul() if gaul2.get(g, -1) == -1]
        assert bad == [], (
            f"{len(bad)} land_gaul cells have gaul2_code == -1 "
            f"(supplemented Azores cells): {sorted(bad)}"
        )

    def test_land_gaul_cells_have_all_seven_fields(self):
        codes = {n: _load(n) for n in ("gaul0_code", "gaul1_code", "gaul2_code")}
        names = {
            n: _load(n)
            for n in ("gaul0_name", "gaul1_name", "gaul2_name", "iso3_code")
        }
        bad = []
        for g in _land_gaul():
            if any(codes[n].get(g, -1) == -1 for n in codes) or any(
                not names[n].get(g) for n in names
            ):
                bad.append(g)
        assert bad == [], (
            f"{len(bad)} land_gaul cells fail full "
            f"completeness: {sorted(bad)}"
        )


@pytest.mark.skipif(not _GAUL_AVAILABLE, reason=_SKIP_REASON)
class TestSentinelOverloading:
    """P7 (SOFT): -1 means 'unassigned' everywhere else; for supplemented
    cells it is reused to mean 'no municipality-level data exists'.

    Two different facts share one sentinel, so downstream code cannot
    distinguish 'cell has no country' from 'cell has a country but FAO has
    no admin2 for it'. The supplement already uses negative synthetic codes
    for gaul1 (-3727..-3730); gaul2 should use the same scheme, never -1.
    """

    def test_supplemented_cells_do_not_reuse_unassigned_sentinel_for_gaul2(self):
        gaul1 = _load("gaul1_code")
        gaul2 = _load("gaul2_code")
        supplemented = [g for g in _land_gaul() if gaul1.get(g, 0) < 0]
        assert supplemented, "expected ADR-043 supplemented cells (negative gaul1_code)"
        overloaded = [g for g in supplemented if gaul2.get(g) == -1]
        assert overloaded == [], (
            f"supplemented cells reuse the -1 'unassigned' sentinel for gaul2_code: "
            f"{sorted(overloaded)} — use a distinct synthetic code instead"
        )


@pytest.mark.skipif(not _GAUL_AVAILABLE, reason=_SKIP_REASON)
class TestSuspectedDefectsResolved:
    """P4 (SOFT): every suspected_data_defect must be either supplemented
    or have a recorded rationale explaining the decision.
    """

    _VALID_RESOLUTIONS = {
        "supplemented", "accepted_uncovered", "reclassified",
    }

    def test_no_suspected_defects_without_resolution(self):
        classification = json.loads(_CLASSIFICATION.read_text())
        gaul0 = _load("gaul0_code")
        unresolved = [
            e["gid"]
            for e in classification
            if e["classification"] == "suspected_data_defect"
            and gaul0.get(e["gid"], -1) == -1
            and e.get("resolution") not in self._VALID_RESOLUTIONS
        ]
        assert unresolved == [], (
            f"cells classified suspected_data_defect lack a "
            f"structured resolution field: {unresolved} — "
            f"supplement them (ADR-043 pattern) or record a "
            f"resolution in {self._VALID_RESOLUTIONS}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
