"""Does production still do what ADR-053 decided, on both axes at once?

ADR-053 (Accepted 2026-11-10) decided that UCDP events whose own
``date_prec`` says the month is unknown should be *allocated* across the
months they span, weighted by observed activity, rather than booked whole
onto their closing month. On 2026-11-10 ``scripts/refresh_pipeline.sh``
moved from ``production_parity`` to ``kgi_kti_activity``, which composes
that decision with ADR-049's spatial one.

**These tests exist because ADR-053's own Validation & Monitoring section
asked for them and nothing implemented it.** Before this file, no test in
the repository referenced ADR-053, ``kgi_kti_activity``, or the seasonality
guard -- so the ADR and the code it governs could have drifted apart in
silence. That is C-365 recurring, and ADR-053 says as much in its own
words: *"A decision with no observer drifts from its code in silence."*

Two of the three observers live here. The third -- the per-build provenance
counters -- belongs in the ledger the builder writes, not in a test, and is
in ``builders/ucdp_v1.py``.

**On skipping.** Both tests need the consolidated store, and the
seasonality guard needs a built viewpoint. Neither is in CI, so these run
at the keyboard and on the server. That is the same limit
``TestAdr049GoldenCriterion`` already has in
``test_adr049_profile_contract.py``, and the numbers measured by hand are
recorded in each docstring so that a skip can never be mistaken for a
pass.
"""

from __future__ import annotations

import re
from pathlib import Path

import pyarrow.compute as pc
import pyarrow.parquet as pq
import pytest

from datafactory_viewpoint.spatial_distribution import (
    get_spatial_distribution,
)
from datafactory_viewpoint.spatial_weights import build_spatial_weight_map
from datafactory_viewpoint.temporal_distribution import get_distribution
from datafactory_viewpoint.temporal_weights import (
    CASCADE_KEYS,
    build_temporal_weight_map,
)

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "data" / "consolidated" / "ucdp_store.parquet"
GAUL1 = ROOT / "data" / "raw" / "gaul_admin" / "gaul1_code.parquet"
GAUL0 = ROOT / "data" / "raw" / "gaul_admin" / "gaul0_code.parquet"

#: The Tigray war's annual aggregate -- ``best`` 113,368, ``date_prec`` 5
#: and ``where_prec`` 5, ``where_description`` "Tigray, Afar, Amhara".
#: A whole year across three Ethiopian regions, delivered as one
#: cell-month. ADR-049 and ADR-053 both name this event and this cell.
TIGRAY_EVENT_ID = 463131
TIGRAY_CENTROID_PGID = 148759
TIGRAY_ARTEFACT_MONTH = "2021-12-01"

#: ADR-053 Validation & Monitoring: "cell 148759 at December 2021 below
#: 1,000". Measured 240 on the 2026-11-06 store build.
TIGRAY_CELL_CEILING = 1_000

#: ADR-053 Validation & Monitoring: "December's share of state-based
#: fatalities must stay below 9.0%". Under ``date_end_only`` it was
#: 12.27%, because every finalised annual summary landed on a December.
DECEMBER_SHARE_CEILING = 9.0

_EXTENSIVE = ("best", "low", "high")
_EVENT_COLUMNS = [
    "id", "best", "low", "high",
    "date_start", "date_end", "date_prec", "where_prec",
    "priogrid_gid", "type_of_violence",
    "_source_type", "_source_version",
    *CASCADE_KEYS,
]


def pipeline_profile() -> str:
    """The allocation profile ``refresh_pipeline.sh`` builds under."""
    script = (ROOT / "scripts" / "refresh_pipeline.sh").read_text()
    match = re.search(
        r'^VIEWPOINT_PROFILE="([^"]+)"', script, re.MULTILINE,
    )
    assert match is not None, (
        "refresh_pipeline.sh has no VIEWPOINT_PROFILE assignment"
    )
    return match.group(1)


# Stays on the real store and the real crosswalks, deliberately. What
# this class asserts is a claim about *this* event in *this* geography
# -- that event 463131's December cell-month comes down below ADR-053's
# ceiling, and that a year across three named Ethiopian regions reaches
# at least ten of their cells. Those are facts about the world, and a
# synthetic polygon cannot stand in for them: a fixture asserting that
# invented cells behave as invented would be mutation category M4,
# conformance to a declaration nothing checks.
#
# The part of this that *is* a property of the code -- composition
# conserves, both stages act, the allocation spreads on both axes --
# is asserted on synthetic geography in
# TestAdr053ComposedOnSyntheticGeographyGreen below, which runs in CI
# (#550).
@pytest.mark.skipif(
    not (STORE.exists() and GAUL1.exists() and GAUL0.exists()),
    reason="needs the consolidated store and the GAUL crosswalks",
)
class TestAdr053ComposedGoldenCriterion:
    """Temporal then spatial, in ADR-053 section 5's order.

    ADR-049's golden test checks the spatial axis alone and ADR-053's
    strategy tests check the temporal axis alone. Neither catches a
    composition defect, and composition is what production now runs: the
    temporal stage emits one row per month, and the spatial stage then
    distributes each month's total across cells. Each stage conserves
    independently, so the composition must conserve exactly too.
    """

    @pytest.fixture(scope="class")
    def store(self):  # type: ignore[no-untyped-def]
        return pq.read_table(STORE, columns=_EVENT_COLUMNS)

    @pytest.fixture(scope="class")
    def temporal_weights(self, store):  # type: ignore[no-untyped-def]
        return build_temporal_weight_map(store)

    @pytest.fixture(scope="class")
    def spatial_weights(self, store):  # type: ignore[no-untyped-def]
        return build_spatial_weight_map(store, GAUL1, GAUL0)

    @pytest.fixture(scope="class")
    def tigray_event(self, store) -> dict:  # type: ignore[no-untyped-def]
        rows = store.filter(
            pc.equal(store["id"], TIGRAY_EVENT_ID)
        ).to_pylist()
        if not rows:
            pytest.skip(
                f"event {TIGRAY_EVENT_ID} absent from this store build"
            )
        return rows[0]

    @pytest.fixture(scope="class")
    def allocated(
        self, tigray_event, temporal_weights, spatial_weights,
    ) -> list[dict]:  # type: ignore[no-untyped-def]
        """Run the event through the production profile's two stages."""
        temporal = get_distribution("activity_weighted")
        spatial = get_spatial_distribution("proportional")
        rows: list[dict] = []
        for month_row in temporal(tigray_event, temporal_weights):
            rows.extend(spatial(month_row, spatial_weights))
        return rows

    def test_the_event_is_still_the_one_the_adrs_describe(
        self, tigray_event: dict,
    ) -> None:
        """Guard the premise before asserting anything about it."""
        assert tigray_event["date_prec"] == 5
        assert tigray_event["where_prec"] == 5
        assert tigray_event["priogrid_gid"] == TIGRAY_CENTROID_PGID
        assert tigray_event["best"] == 113_368
        assert str(tigray_event["date_start"]).startswith("2021-01")
        assert str(tigray_event["date_end"]).startswith("2021-12")

    def test_composition_conserves_every_extensive_field_exactly(
        self, tigray_event: dict, allocated: list[dict],
    ) -> None:
        """Exactly, not approximately -- these are integer death counts.

        ADR-040's conservation invariant, through both stages. ``ceil_split``
        (the strategy production ran until 2026-11-10) could not pass this:
        it assigns ``ceil(best/span)`` per month and so reports more deaths
        than the source recorded, measured at 96 across 74 events (C-367).
        """
        for field in _EXTENSIVE:
            expected = int(tigray_event[field] or 0)
            got = sum(int(row[field] or 0) for row in allocated)
            assert got == expected, (
                f"{field}: allocated {got:,} against the source's "
                f"{expected:,} -- composition is not conserving"
            )

    def test_the_artefact_cell_month_collapses(
        self, allocated: list[dict],
    ) -> None:
        """The thing #533 is actually about.

        Measured 240 on the 2026-11-06 store, against 113,395 delivered
        under ``production_parity``. The ceiling is ADR-053's number, not
        the measurement, so this stays meaningful as the store grows.
        """
        in_cell_month = sum(
            int(row["best"] or 0)
            for row in allocated
            if row["priogrid_gid"] == TIGRAY_CENTROID_PGID
            and str(row["date_month"]) == TIGRAY_ARTEFACT_MONTH
        )
        assert in_cell_month < TIGRAY_CELL_CEILING, (
            f"cell {TIGRAY_CENTROID_PGID} at {TIGRAY_ARTEFACT_MONTH} holds "
            f"{in_cell_month:,}, at or above ADR-053's ceiling of "
            f"{TIGRAY_CELL_CEILING:,}"
        )

    def test_the_event_occupies_the_span_it_declares(
        self, allocated: list[dict],
    ) -> None:
        """A year across three regions must not be one cell-month.

        Measured 12 months x 18 cells. Asserted as lower bounds: a month
        with no observed activity legitimately receives zero and is not
        emitted (ADR-053's stated assumption, and the one most likely to
        be wrong), so an exact count would be brittle by design.
        """
        months = {str(row["date_month"]) for row in allocated}
        cells = {row["priogrid_gid"] for row in allocated}
        assert len(months) >= 10, (
            f"allocated into {len(months)} months; the event declares a "
            f"12-month span and activity weighting should reach most of it"
        )
        assert len(cells) >= 10, (
            f"allocated into {len(cells)} cells; the event declares three "
            f"admin-1 regions and ADR-049 distributes across their cells"
        )

    def test_no_row_is_marked_undistributed(
        self, allocated: list[dict],
    ) -> None:
        """Both stages must have claimed this event, not just one.

        A composition bug that silently ran one stage would still conserve
        and could still look spread. The annotations are how each stage
        says it acted.
        """
        assert all(row.get("_temporal_distributed") for row in allocated), (
            "some rows carry no _temporal_distributed marker -- the "
            "temporal stage did not allocate this event"
        )
        # `all`, not `any`: proportional() marks every row it emits
        # (spatial_distribution.proportional sets the flag inside the
        # per-cell loop), and the temporal stage carries the field
        # through with **event. So a single unmarked row means some
        # row reached the output by another path. `any` was the
        # original spelling and the #555 audit showed it passes when
        # only one row in the whole allocation is marked.
        assert all(row.get("_spatial_distributed") for row in allocated), (
            "a row carries no _spatial_distributed marker -- the spatial "
            "stage did not distribute this event off its centroid, or "
            "some row reached the output without passing through it"
        )


class TestAdr053ComposedOnSyntheticGeographyGreen:
    """The composition's own properties, in CI, on invented geography.

    ``TestAdr053ComposedGoldenCriterion`` above cannot run in CI: it
    needs the consolidated store and the GAUL crosswalks, and
    ``.gitignore`` keeps both out. That is how the delivery defect
    shipped -- the observers existed and never executed (#550, M6).

    What is asserted here is only what does not depend on real
    geography: that running ADR-053's temporal stage and ADR-049's
    spatial stage in that order conserves every extensive field
    exactly, that both stages mark the rows they touched, and that the
    result spreads on both axes rather than one. The claims that *are*
    about Ethiopia stay above, on real data.
    """

    @pytest.fixture
    def fixture(self, tmp_path: Path) -> dict:
        from conftest import load_synthetic_generator

        gen = load_synthetic_generator()
        gaul = gen.write_synthetic_gaul(tmp_path / "gaul_admin")
        events_path = tmp_path / "events.parquet"
        rows = gen.write_synthetic_ucdp_events(events_path)
        table = pq.read_table(events_path)
        return {
            "gen": gen,
            "event": next(
                r for r in rows if r["id"] == gen.SUMMARY_EVENT_ID
            ),
            "temporal": build_temporal_weight_map(table),
            "spatial": build_spatial_weight_map(
                table, gaul["gaul1_code"], gaul["gaul0_code"],
            ),
        }

    @pytest.fixture
    def allocated(self, fixture: dict) -> list[dict]:
        """Temporal then spatial, in ADR-053 section 5's order."""
        temporal = get_distribution("activity_weighted")
        spatial = get_spatial_distribution("proportional")
        rows: list[dict] = []
        for month_row in temporal(
            fixture["event"], fixture["temporal"],
        ):
            rows.extend(spatial(month_row, fixture["spatial"]))
        return rows

    def test_composition_conserves_every_extensive_field_exactly(
        self, fixture: dict, allocated: list[dict],
    ) -> None:
        for field in _EXTENSIVE:
            expected = int(fixture["event"][field] or 0)
            got = sum(int(row[field] or 0) for row in allocated)
            assert got == expected, (
                f"{field}: allocated {got:,} against the source's "
                f"{expected:,} -- composition is not conserving"
            )

    def test_the_allocation_spreads_on_both_axes(
        self, fixture: dict, allocated: list[dict],
    ) -> None:
        """Equalities, because the fixture is fully determined.

        The synthetic pool holds one precise event per well-located
        cell, dated to the first eight months of 2021, and the summary
        event's polygon has six weighted cells. A bound would hide a
        stage that stopped halfway; the planted numbers do not.
        """
        gen = fixture["gen"]
        months = {str(row["date_month"]) for row in allocated}
        cells = tuple(sorted({row["priogrid_gid"] for row in allocated}))
        assert len(months) == 8, sorted(months)
        assert cells == gen.ADMIN1_ALLOCATION_CELLS, cells

    def test_both_stages_marked_the_rows_they_touched(
        self, allocated: list[dict],
    ) -> None:
        """A composition that silently ran one stage still conserves."""
        assert all(
            row.get("_temporal_distributed") for row in allocated
        ), "the temporal stage did not allocate this event"
        # `all`, not `any` -- see the sibling assertion in
        # TestAdr053ComposedGoldenCriterion for why.
        assert all(
            row.get("_spatial_distributed") for row in allocated
        ), "the spatial stage did not distribute off the centroid"

    def test_no_cell_month_holds_the_whole_event(
        self, fixture: dict, allocated: list[dict],
    ) -> None:
        """The artefact ADR-053 exists to remove, stated structurally.

        The real criterion is a number about cell 148759 in December
        2021 and belongs on real data. What holds on any geography is
        that an event declaring a year and a multi-cell polygon must
        not arrive as a single cell-month.
        """
        worst = max(
            sum(
                int(r["best"] or 0)
                for r in allocated
                if r["priogrid_gid"] == pgid
                and str(r["date_month"]) == month
            )
            for pgid in {r["priogrid_gid"] for r in allocated}
            for month in {str(r["date_month"]) for r in allocated}
        )
        total = int(fixture["event"]["best"] or 0)
        assert worst < total, (
            f"one cell-month holds {worst:,} of {total:,}"
        )


def _synthetic_event(
    event_id: int,
    *,
    date_start: str,
    date_end: str,
    date_prec: int,
    best: int,
    dyad: int,
    country_id: int = 200,
) -> dict:
    """One consolidated event, with the columns the cascade needs.

    ``build_temporal_weight_map`` raises ``KeyError`` when a cascade
    column is absent rather than producing an empty indicator that would
    send every allocation to uniform (ADR-011), so all four are set.
    """
    return {
        "id": event_id,
        "dyad_new_id": dyad,
        "conflict_new_id": dyad,
        "side_b_new_id": dyad,
        "country_id": country_id,
        "country": "Sudan",
        "latitude": 4.0,
        "longitude": 31.5,
        "date_start": date_start,
        "date_end": date_end,
        "date_prec": date_prec,
        "best": best,
        # Distinct from best on purpose -- see the comment in
        # scripts/generate_synthetic_data.py's _synthetic_event. With
        # all three equal, the _EXTENSIVE conservation loop above is
        # one assertion run three times (#555 audit survivor M-06).
        "low": best // 3,
        "high": best * 2 + 1,
        "type_of_violence": 1,
        "where_prec": 1,
        "priogrid_gid": 150000,
        "_source_type": "annual",
        "_source_version": "25.1",
        "_ingested_at": "2026-03-21T10:00:00Z",
    }


class TestAdr053ProvenanceCounters:
    """ADR-053's third observer: the ledger must say what it did.

    *"Provenance counters on every build: how many events were temporally
    distributed, the distribution of ``_temporal_weight_key`` across
    cascade levels, and how many fell back to uniform."* Before this the
    ledger recorded ``temporal_activity_pool_events`` and nothing else
    about the temporal stage, so the fallback rate -- the number that
    says whether activity weighting is actually earning its assumption --
    was unobservable in production.

    Synthetic, so this one runs in CI rather than waiting for data.
    """

    @pytest.fixture
    def ledger_entry(self, tmp_path: Path) -> dict:
        import json

        import pyarrow as pa

        from datafactory_viewpoint.builders.ucdp_v1 import build_ucdp_v1
        from datafactory_viewpoint.viewpoint_config import ViewpointConfig

        events = [
            # Precisely dated and located, so these are the activity
            # pool: dyad 10 fought in February and March, nowhere else.
            _synthetic_event(
                1, date_start="2023-02-10", date_end="2023-02-10",
                date_prec=1, best=50, dyad=10,
            ),
            _synthetic_event(
                2, date_start="2023-03-10", date_end="2023-03-10",
                date_prec=1, best=50, dyad=10,
            ),
            # Month unknown, spanning Jan-Apr, same dyad -- allocates on
            # dyad 10's observed pattern.
            _synthetic_event(
                3, date_start="2023-01-01", date_end="2023-04-30",
                date_prec=5, best=100, dyad=10,
            ),
            # Month unknown, but no cascade level has any activity, so
            # this is the uniform fallback.
            _synthetic_event(
                4, date_start="2023-01-01", date_end="2023-04-30",
                date_prec=5, best=40, dyad=99, country_id=999,
            ),
        ]
        fields = sorted({k for ev in events for k in ev})
        store = tmp_path / "store.parquet"
        pq.write_table(
            pa.table({
                f: pa.array([ev.get(f) for ev in events], from_pandas=True)
                for f in fields
            }),
            store,
        )
        ledger = tmp_path / "ledger.jsonl"
        build_ucdp_v1(ViewpointConfig(
            consolidated_path=store,
            output_path=tmp_path / "viewpoint.parquet",
            ledger_path=ledger,
            distribution_strategy="activity_weighted",
            spatial_distribution_strategy="passthrough",
        ))
        return json.loads(ledger.read_text().strip().splitlines()[-1])

    def test_counts_only_the_events_it_allocated(
        self, ledger_entry: dict,
    ) -> None:
        """Two of the four events have an unknown month, not all four."""
        assert ledger_entry["n_temporally_distributed"] == 2

    def test_records_which_cascade_level_supplied_the_weights(
        self, ledger_entry: dict,
    ) -> None:
        assert ledger_entry["temporal_weight_key_counts"] == {
            "dyad_new_id": 1,
            "uniform_fallback": 1,
        }

    def test_the_fallback_count_is_stated_not_inferred(
        self, ledger_entry: dict,
    ) -> None:
        """A reader should not have to know the sentinel's name.

        This is the counter ADR-053 actually names, and the one worth
        monitoring: a rising fallback share means activity weighting is
        choosing flat weights more often, which is the assumption it
        exists to improve on quietly stopping to apply.
        """
        assert ledger_entry["n_temporal_uniform_fallback"] == 1


class TestAdr053SeasonalityGuard:
    """December must stop being an artefact of the allocation rule.

    ``date_end_only`` put every finalised annual summary on its closing
    month, and UCDP closes annual records on 31 December, so December
    carried **12.27%** of all state-based fatalities against 8.33% for an
    even year. October carried 13.33% for the same reason one rung down.

    Measured by hand on the 2026-11-06 build, state-based only:

    - ``production_parity``: December **12.27%**, spread 6.99 pp, peak
      month October at 13.33%
    - ``kgi_kti_activity``: December **6.62%**, spread 4.67 pp, peak month
      **August at 11.30%**

    **The honest caveat, recorded here rather than left for someone to
    find:** the peak does not disappear, it moves. August rises from 6.66%
    to 11.30%, mostly from event 463137 (121,848 deaths, 2022-08-24 to
    2022-10-24) relocating to the months where precisely-dated fighting
    was actually observed. That is the mechanism doing what it says on the
    tin -- it borrows the shape of well-observed events -- and it is not
    the same thing as a calendar artefact. But August is now the largest
    month, and anyone who reads the December win as "seasonality is fixed"
    has read too much into it.
    """

    @pytest.fixture(scope="class")
    def viewpoint_path(self) -> Path:
        path = (
            ROOT / "data" / "viewpoint"
            / f"{pipeline_profile()}.parquet"
        )
        if not path.exists():
            pytest.skip(
                f"no built viewpoint at {path} -- this guard runs where a "
                f"pipeline has run"
            )
        return path

    def test_december_is_not_carrying_the_annual_summaries(
        self, viewpoint_path: Path,
    ) -> None:
        table = pq.read_table(
            viewpoint_path,
            columns=["priogrid_gid", "best", "date_month",
                     "type_of_violence"],
        ).to_pandas()
        state_based = table[
            (table.priogrid_gid >= 1) & (table.type_of_violence == 1)
        ]
        calendar_month = state_based.date_month.str.slice(5, 7).astype(int)
        by_month = state_based.groupby(calendar_month).best.sum()
        december_share = 100 * by_month[12] / by_month.sum()
        assert december_share < DECEMBER_SHARE_CEILING, (
            f"December holds {december_share:.2f}% of state-based "
            f"fatalities, at or above ADR-053's {DECEMBER_SHARE_CEILING}% "
            f"ceiling. Under date_end_only this was 12.27%. If the "
            f"allocation is working, this number is near 8.33%. Do not "
            f"raise the ceiling -- it is the ADR's pre-registered "
            f"falsifier."
        )
