"""Does the code still do what ADR-049 decided, and say which profile does it?

ADR-049 (Accepted 2026-06-28) decided that geographically imprecise UCDP
events should be *distributed* across their target polygon rather than
dumped on a centroid cell, and called that this data factory's recommended
behaviour. ``ViewpointConfig`` honours it: ``spatial_distribution_strategy``
defaults to ``"proportional"``.

For four months nothing connected that decision to anything runnable. The
only registered profile was ``production_parity``, which overrides the
default back to ``"passthrough"`` for VIEWSER parity, and **no test asserted
either choice** -- so the ADR and the invoked configuration drifted apart in
silence and the ADR's own acceptance criterion went unchecked. That is C-365
recurring: a decision with nothing watching it.

These tests are the watcher. They pin three things that must not move
without someone deciding they should:

1. ``production_parity`` keeps reproducing VIEWSER (every strategy field).
2. ``kgi_distributed`` differs from it in exactly the KGI concern.
3. ADR-049's own golden criterion actually holds -- the Tigray cell's share
   collapses under distribution, and the total is conserved exactly.

Breaking any one of them should turn this file red. That was checked by
hand when it was written; see the PR.
"""

from __future__ import annotations

from pathlib import Path

import pyarrow.compute as pc
import pyarrow.parquet as pq
import pytest

from datafactory_viewpoint.profiles import PROFILES
from datafactory_viewpoint.spatial_distribution import (
    get_spatial_distribution,
)
from datafactory_viewpoint.spatial_weights import build_spatial_weight_map
from datafactory_viewpoint.viewpoint_config import ViewpointConfig

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "data" / "consolidated" / "ucdp_store.parquet"
GAUL1 = ROOT / "data" / "raw" / "gaul_admin" / "gaul1_code.parquet"
GAUL0 = ROOT / "data" / "raw" / "gaul_admin" / "gaul0_code.parquet"

#: The Tigray war's annual aggregate: ``best`` 113,368 fatalities,
#: ``date_prec`` 5 and ``where_prec`` 5, ``where_description`` "Tigray,
#: Afar, Amhara" -- three Ethiopian regions and a whole year, assigned to
#: one 0.5-degree cell. ADR-049 names this event and this cell.
TIGRAY_EVENT_ID = 463131
TIGRAY_CENTROID_PGID = 148759


class TestProductionParityIsPinned:
    """``production_parity`` is a contract, so its fields are assertions."""

    def test_production_parity_pins_its_strategies(self) -> None:
        profile = PROFILES["production_parity"]
        # Each of these reproduces a specific legacy GedLoader behaviour.
        # Changing one is a parity break and must be a decision, not a
        # diff nobody noticed.
        assert profile["survivorship_strategy"] == "dot9_wins"
        assert profile["distribution_strategy"] == "ceil_split"
        assert profile["spatial_distribution_strategy"] == "passthrough"
        assert profile["source_distribution_map"] == {
            "annual": "date_end_only",
        }
        assert profile["filter_stale_versions"] is True
        assert profile["min_priogrid_gid"] == 1
        assert profile["max_type_of_violence"] == 3
        assert profile["exclude_where_prec"] == (4, 6)

    def test_build_viewpoint_still_defaults_to_parity(self) -> None:
        """Switching what production runs must be deliberate.

        ``kgi_distributed`` existing is not the same as it being invoked.
        If this assertion is ever changed, every published grid-level
        fatality figure moves, so the change belongs in a PR of its own.
        """
        source = (ROOT / "scripts" / "build_viewpoint.py").read_text()
        assert 'default="production_parity"' in source, (
            "scripts/build_viewpoint.py no longer defaults to "
            "production_parity -- that moves every published fatality "
            "figure and needs an explicit decision (ADR-049 section 6)"
        )


class TestAdr049IsHonouredByTheDefault:
    """ADR-049 section 6: distribution is the recommended behaviour."""

    def test_config_default_is_proportional(self) -> None:
        assert ViewpointConfig.spatial_distribution_strategy == (
            "proportional"
        ), (
            "ADR-049 section 6 makes spatial distribution the recommended "
            "default. If this changes, amend the ADR -- do not leave the "
            "code and the decision disagreeing."
        )

    def test_kgi_distributed_exists_and_is_registered(self) -> None:
        assert "kgi_distributed" in PROFILES, (
            "ADR-049's recommended behaviour needs a profile name, or it "
            "cannot be selected, tested end to end, or compared against "
            "parity"
        )

    def test_kgi_distributed_differs_only_in_kgi_handling(self) -> None:
        """One concern, two fields, nothing else.

        The temporal axis is deliberately identical to parity: that is a
        separate experiment with its own literature, and ``Denton (1971)``
        has already ruled out the obvious candidate.
        """
        parity = PROFILES["production_parity"]
        kgi = PROFILES["kgi_distributed"]
        expected = {
            "spatial_distribution_strategy",
            "exclude_where_prec",
            "version",
        }
        actual = {
            key
            for key in set(parity) | set(kgi)
            if parity.get(key) != kgi.get(key)
        }
        assert actual == expected, (
            f"kgi_distributed should differ from production_parity in "
            f"exactly {sorted(expected)}, but differs in {sorted(actual)}"
        )
        assert kgi["spatial_distribution_strategy"] == "proportional"
        assert kgi["exclude_where_prec"] == ()


@pytest.mark.skipif(
    not (STORE.exists() and GAUL1.exists() and GAUL0.exists()),
    reason=(
        "needs the consolidated UCDP store and the GAUL crosswalks; "
        "skipped rather than failed because the environment cannot "
        "answer the question (C-320)"
    ),
)
class TestAdr049GoldenCriterion:
    """ADR-049 Validation: the Tigray cell's total must come down.

    The ADR states the criterion directionally -- cell 148759 "should drop
    ... to its proportional share within the Tigray admin-1 region" and the
    region must still sum to the original. These tests assert exactly that,
    rather than a fixed number, so they stay meaningful as the store grows.
    """

    @pytest.fixture(scope="class")
    def weight_map(self):  # type: ignore[no-untyped-def]
        table = pq.read_table(
            STORE,
            columns=[
                "id",
                "best",
                "low",
                "high",
                "where_prec",
                "priogrid_gid",
                "type_of_violence",
                "_source_type",
                "_source_version",
            ],
        )
        return build_spatial_weight_map(table, GAUL1, GAUL0)

    @pytest.fixture(scope="class")
    def tigray_event(self) -> dict:
        table = pq.read_table(
            STORE,
            columns=[
                "id",
                "best",
                "low",
                "high",
                "where_prec",
                "priogrid_gid",
            ],
        )
        mask = pc.equal(table["id"], TIGRAY_EVENT_ID)
        rows = table.filter(mask).to_pylist()
        if not rows:
            pytest.skip(
                f"event {TIGRAY_EVENT_ID} absent from this store build"
            )
        return rows[0]

    def test_event_is_still_the_one_adr_049_described(
        self, tigray_event: dict
    ) -> None:
        """Guard the premise before asserting the conclusion."""
        assert tigray_event["where_prec"] == 5
        assert tigray_event["priogrid_gid"] == TIGRAY_CENTROID_PGID
        assert tigray_event["best"] > 100_000

    def test_tigray_cell_drops_under_distribution(
        self, tigray_event: dict, weight_map
    ) -> None:  # type: ignore[no-untyped-def]
        """The centroid's share must fall -- but see the next test.

        On its own this assertion is weak: a strategy that dumped the whole
        total onto some *other* single cell would leave this one at zero and
        pass. That mutation was applied and did survive this check, which is
        why ``test_allocation_is_proportional_to_the_weight_map`` exists.
        Kept because it is ADR-049's criterion in the ADR's own words.
        """
        proportional = get_spatial_distribution("proportional")
        rows = proportional(tigray_event, weight_map)

        assert len(rows) > 1, (
            "ADR-049's whole decision is that this event stops landing on "
            "one cell; it produced a single row"
        )

        by_cell = {row["priogrid_gid"]: row["best"] for row in rows}
        assert TIGRAY_CENTROID_PGID in by_cell

        original = int(tigray_event["best"])
        centroid_share = by_cell[TIGRAY_CENTROID_PGID] / original
        assert centroid_share < 0.25, (
            f"cell {TIGRAY_CENTROID_PGID} still absorbs "
            f"{centroid_share:.1%} of the event; ADR-049 requires it to "
            f"fall to its proportional share of the region"
        )

    def test_allocation_is_proportional_to_the_weight_map(
        self, tigray_event: dict, weight_map
    ) -> None:  # type: ignore[no-untyped-def]
        """Mass must land where the weights say, not merely leave the cell.

        This is the assertion with teeth. ADR-049 section 3 defines the
        allocation as ``event_best * cell_share``, so every cell's
        allocation is predicted exactly up to the floor+remainder rounding
        in ``_distribute_value`` -- at most one fatality either way.

        A strategy that spreads the total arbitrarily, or concentrates it on
        a different single cell, fails here even though it passes the
        "centroid share fell" check above.
        """
        proportional = get_spatial_distribution("proportional")
        rows = proportional(tigray_event, weight_map)

        gaul_code = weight_map.pgid_to_gaul1[TIGRAY_CENTROID_PGID]
        weights = weight_map.admin1_weights[gaul_code]
        total = int(tigray_event["best"])

        by_cell = {row["priogrid_gid"]: row["best"] for row in rows}
        assert set(by_cell) == set(weights), (
            "the distributed cells are not the weighted cells of the "
            "target polygon"
        )

        nonzero = [pgid for pgid, v in by_cell.items() if v > 0]
        assert len(nonzero) > 1, (
            f"only {len(nonzero)} cell(s) received a nonzero allocation; "
            f"the total was moved, not distributed"
        )

        for pgid, weight in weights.items():
            expected = weight * total
            assert abs(by_cell[pgid] - expected) <= 1.0, (
                f"cell {pgid} got {by_cell[pgid]} but its weight "
                f"{weight:.6f} predicts {expected:.2f}; allocation is not "
                f"proportional to the weight map"
            )

    def test_distribution_conserves_the_total_exactly(
        self, tigray_event: dict, weight_map
    ) -> None:  # type: ignore[no-untyped-def]
        """ADR-040 Invariant 1 and ADR-049 section 5, on one real event."""
        proportional = get_spatial_distribution("proportional")
        rows = proportional(tigray_event, weight_map)
        for field in ("best", "low", "high"):
            assert sum(row[field] for row in rows) == int(
                tigray_event[field] or 0
            ), f"{field} is not conserved across the distributed cells"

    def test_passthrough_still_does_not_distribute(
        self, tigray_event: dict, weight_map
    ) -> None:  # type: ignore[no-untyped-def]
        """The control. Parity must keep behaving as parity."""
        passthrough = get_spatial_distribution("passthrough")
        rows = passthrough(tigray_event, weight_map)
        assert len(rows) == 1
        assert rows[0]["priogrid_gid"] == TIGRAY_CENTROID_PGID
        assert rows[0]["best"] == tigray_event["best"]
