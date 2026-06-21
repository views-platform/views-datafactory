"""Falsification tests — round 2 audit of ADR-043 supplement claims.

Round 1 findings (C-g1 completeness-keyed region, C-g2 self-deactivation
guard, sentinel overloading) were fixed structurally. Round 2 audited the
reclassification rationale, guard testability, and upstream reporting.
"""

import json
from pathlib import Path

import pyarrow.parquet as pq
import pytest
import shapefile

_GAUL_DIR = Path("data/raw/gaul_admin")
_L1_SHP = _GAUL_DIR / "shapefiles/GAUL_2024_L1/GAUL_2024_L1.shp"
_CLASSIFICATION = Path(
    "reports/investigation_gaul_excluded_cells/excluded_cell_classification.json"
)
_ADR_043 = Path("docs/ADRs/043_gaul_azores_supplement.md")

# Maldives has 21 administrative atolls; Gnaviyani (Fuvahmulah, ~13k
# inhabitants, PRIO-GRID cell 129387) is one of them.
_GNAVIYANI_SPELLINGS = ("gnaviyani", "fuvah", "fuvam", "foammul", "foah")
_FUVAHMULAH_GID = 129387


def _gaul0(gid: int) -> int:
    t = pq.read_table(_GAUL_DIR / "gaul0_code.parquet")
    return dict(
        zip(t.column("gid").to_pylist(), t.column("value").to_pylist(), strict=True)
    ).get(gid, -1)


@pytest.mark.skipif(
    not _L1_SHP.exists(),
    reason="GAUL L1 shapefile not available — data/ is gitignored",
)
class TestReclassificationRationaleIsFactual:
    """R2-P3 (HARD): a registry rationale must not be contradicted by the data.

    The blanket reclassification of 67 cells to 'coastal_resolution_gap'
    states: "True source defects (ADR-043 Azores) have entire named
    landmasses absent from the shapefile." Gnaviyani (Fuvahmulah) is an
    entire named administrative atoll absent from GAUL 2024 L1 and L2 under
    every spelling — it meets the rationale's own definition of a true
    source defect, yet its cell was reclassified as a resolution artifact
    and resolved 'accepted_uncovered'. The discriminator used (distance to
    the NEAREST polygon) conflates 'my polygon has coarse edges' (e.g.
    Kiritimati — GAUL has the polygon) with 'my polygon does not exist but
    a neighbour's is nearby' (Fuvahmulah — nearest is Seenu, a different
    atoll).

    Passes when cell 129387 is either supplemented (ADR-043 pattern; NE 10m
    has the Gnaviyani polygon — verified) or re-reclassified as a source
    defect with a factually accurate rationale and a recorded decision.
    """

    def test_fuvahmulah_not_classified_as_resolution_gap(self):
        sf = shapefile.Reader(str(_L1_SHP))
        fields = [f[0] for f in sf.fields[1:]]
        gaul_has_gnaviyani = any(
            any(
                s in str(
                    dict(zip(fields, rec, strict=True))
                    .get("gaul1_name", "")
                ).lower()
                for s in _GNAVIYANI_SPELLINGS
            )
            for rec in sf.iterRecords()
            if dict(zip(fields, rec, strict=True))
            .get("gaul0_name") == "Maldives"
        )
        entry = next(
            e for e in json.loads(_CLASSIFICATION.read_text())
            if e["gid"] == _FUVAHMULAH_GID
        )
        supplemented = _gaul0(_FUVAHMULAH_GID) != -1
        misclassified = (
            not gaul_has_gnaviyani
            and not supplemented
            and entry["classification"] == "coastal_resolution_gap"
        )
        assert not misclassified, (
            "gid 129387 (Fuvahmulah): GAUL 2024 contains no Gnaviyani unit "
            "(20 of 21 Maldivian atolls present), so by the rationale's own "
            "criterion this is a source defect, not a resolution gap. "
            "Supplement it (NE 10m has the polygon) or reclassify with a "
            "factually accurate rationale."
        )


class TestSupplementGuardIsTestable:
    """R2-P6 (SOFT): the C-g2 self-deactivation guard has zero test coverage —
    because it is inlined in main() (generate_area_majority_gaul.py:344-379)
    with no seam to test through.

    Passes when the guard is extracted as a callable (e.g.
    _filter_covered_supplements(polygons, sup_polys, sup_recs)) and a test
    exercises both paths: GAUL-covers-supplement -> skipped+logged, and
    GAUL-lacks-supplement -> kept.
    """

    def test_guard_is_extracted_and_importable(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "gen_gaul", "scripts/generate_area_majority_gaul.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert hasattr(mod, "_filter_covered_supplements"), (
            "Guard logic is inlined in main() — extract it so the "
            "GAUL-update interaction (C-g2) can be tested. The highest-"
            "regret future failure currently has zero coverage."
        )


class TestUpstreamDefectIsReported:
    """R2-P7 (SOFT): the supplement patches FAO's product locally, but no
    communication trail exists — no FAO defect report reference, no release-
    note item for the synthetic codes FAO will receive.

    GAUL 2024 missing Sao Miguel (140k inhabitants) and Gnaviyani is FAO's
    defect to fix at source; supplements are designed to self-retire when
    they do (the guard) — but only if FAO knows.

    Passes when ADR-043 records the upstream report (issue/email/contact
    reference) and the FAO release-note obligation for negative synthetic
    codes.
    """

    def test_adr_records_upstream_report_and_release_note(self):
        text = _ADR_043.read_text().lower()
        has_report = any(
            k in text
            for k in (
                "reported to fao",
                "upstream report",
                "defect report",
            )
        )
        has_release_note = "release note" in text or "release-note" in text
        assert has_report and has_release_note, (
            "ADR-043 lacks a communication trail: "
            f"upstream report={has_report}, "
            f"release-note={has_release_note}"
        )


class TestFilterCoveredSupplements:
    """Exercise both paths of _filter_covered_supplements."""

    def test_uncovered_supplement_is_kept(self):
        import importlib.util

        from shapely.geometry import box as shapely_box

        spec = importlib.util.spec_from_file_location(
            "gen_gaul",
            "scripts/generate_area_majority_gaul.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        gaul = [shapely_box(0, 0, 1, 1)]
        sup = [shapely_box(10, 10, 11, 11)]
        recs = [{"gaul1_name": "Far away island"}]
        kept_p, kept_r = mod._filter_covered_supplements(
            gaul, sup, recs,
        )
        assert len(kept_p) == 1
        assert kept_r[0]["gaul1_name"] == "Far away island"

    def test_covered_supplement_is_skipped(self):
        import importlib.util

        from shapely.geometry import box as shapely_box

        spec = importlib.util.spec_from_file_location(
            "gen_gaul",
            "scripts/generate_area_majority_gaul.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        gaul = [shapely_box(0, 0, 10, 10)]
        sup = [shapely_box(1, 1, 2, 2)]
        recs = [{"gaul1_name": "Already covered"}]
        kept_p, kept_r = mod._filter_covered_supplements(
            gaul, sup, recs,
        )
        assert len(kept_p) == 0
        assert len(kept_r) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
