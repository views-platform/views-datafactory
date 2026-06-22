"""Contract tests for region/coverage alignment (#215).

Verifies that africa_me_gaul is a subset of land_gaul (the
consumer guarantee) and that the known excluded cells are exactly
the 5 cells absent from land_gaul in the legacy set.
"""

from __future__ import annotations

from datafactory_query.regions import load_region_pgids


class TestRegionCoverageMismatch:

    def test_africa_me_gaul_subset_of_land_gaul(self) -> None:
        africa_me_gaul = load_region_pgids("africa_me_gaul")
        land_gaul = load_region_pgids("land_gaul")
        overflow = africa_me_gaul - land_gaul
        assert overflow == set(), (
            f"africa_me_gaul contains {len(overflow)} cells "
            f"absent from land_gaul: {sorted(overflow)}"
        )

    def test_legacy_minus_land_gaul_is_known_set(self) -> None:
        legacy = load_region_pgids("africa_me_legacy")
        land_gaul = load_region_pgids("land_gaul")
        excluded = legacy - land_gaul
        assert excluded == {62356, 94776, 99027, 107733, 107742}, (
            f"Expected 5 known excluded cells, got {sorted(excluded)}"
        )

    def test_africa_me_gaul_equals_legacy_intersect_land_gaul(self) -> None:
        legacy = load_region_pgids("africa_me_legacy")
        land_gaul = load_region_pgids("land_gaul")
        africa_me_gaul = load_region_pgids("africa_me_gaul")
        assert africa_me_gaul == legacy & land_gaul
