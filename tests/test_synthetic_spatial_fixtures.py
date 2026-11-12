"""Synthetic geography and events, so the spatial guards can run in CI.

Story 3 of epic #547 (issue #550). The delivery defect that epic exists
to fix shipped because the tests that would have caught it cannot run
in CI: every test exercising the spatial allocator against real
geography is ``skipif``'d on the GAUL crosswalks, and ``.gitignore``
guarantees CI has none of ``data/``. Mutation category **M6 --
correct, and never runs.**

This module is the fixture's own test. It asserts that
``scripts/generate_synthetic_data.py``'s synthetic crosswalks and
events are well-formed, that the real ``build_spatial_weight_map`` and
``proportional`` run against them, and -- the point of the story --
that they do so with no file under ``data/`` reachable.

It is green on its own. The guards that stay red until the seam is
closed live in ``test_falsification_spatial_allocation_delivery.py``.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import pytest
from conftest import load_synthetic_generator

from datafactory_priogrid.cell_generator import latlon_to_pgid
from datafactory_priogrid.grid_config import DEFAULT_GRID_CONFIG
from datafactory_viewpoint.spatial_distribution import (
    get_spatial_distribution,
)
from datafactory_viewpoint.spatial_weights import build_spatial_weight_map
from datafactory_viewpoint.temporal_weights import (
    CASCADE_KEYS,
    build_temporal_weight_map,
)

_GEN = load_synthetic_generator()


@pytest.fixture
def fixtures(tmp_path: Path) -> dict:
    """Write the synthetic crosswalks and events under tmp_path."""
    gaul = _GEN.write_synthetic_gaul(tmp_path / "gaul_admin")
    events_path = tmp_path / "events.parquet"
    rows = _GEN.write_synthetic_ucdp_events(events_path)
    return {
        "gaul0": gaul["gaul0_code"],
        "gaul1": gaul["gaul1_code"],
        "events_path": events_path,
        "rows": rows,
    }


def _event(rows: list[dict], event_id: int) -> dict:
    matches = [r for r in rows if r["id"] == event_id]
    assert len(matches) == 1, (
        f"expected exactly one event {event_id}, got {len(matches)}"
    )
    return matches[0]


class TestSyntheticGaulCrosswalksGreen:
    """The crosswalk pair must be shaped like the real files."""

    def test_both_crosswalks_are_written(self, fixtures: dict) -> None:
        assert fixtures["gaul0"].exists()
        assert fixtures["gaul1"].exists()

    def test_schema_matches_the_real_crosswalks(
        self, fixtures: dict,
    ) -> None:
        """Two columns named gid and value, nothing else.

        ``spatial_weights._load_gaul_crosswalk`` reads exactly these
        two by name. A fixture with a different schema would need the
        production loader changed to accommodate it, which would mean
        the guards no longer exercise the code that runs in production.
        """
        for key in ("gaul0", "gaul1"):
            names = pq.read_table(fixtures[key]).column_names
            assert names == ["gid", "value"], (
                f"{key} schema is {names}"
            )

    def test_polygons_are_as_planted(self, fixtures: dict) -> None:
        """Each planted cell carries the admin-1 code it was given."""
        table = pq.read_table(fixtures["gaul1"])
        mapping = dict(zip(
            table.column("gid").to_pylist(),
            table.column("value").to_pylist(),
            strict=True,
        ))
        for pgid in _GEN.GAUL1_POLYGON_A:
            assert mapping[pgid] == _GEN.GAUL1_CODE_A
        for pgid in _GEN.GAUL1_POLYGON_B:
            assert mapping[pgid] == _GEN.GAUL1_CODE_B

    def test_both_polygons_lie_in_one_country(
        self, fixtures: dict,
    ) -> None:
        """Required for a where_prec=6 allocation to span them both."""
        table = pq.read_table(fixtures["gaul0"])
        mapping = dict(zip(
            table.column("gid").to_pylist(),
            table.column("value").to_pylist(),
            strict=True,
        ))
        cells = (*_GEN.GAUL1_POLYGON_A, *_GEN.GAUL1_POLYGON_B)
        assert {mapping[p] for p in cells} == {_GEN.GAUL0_CODE}

    def test_every_planted_cell_round_trips_through_its_centroid(
        self,
    ) -> None:
        """pgid -> centroid -> pgid must be the identity.

        The compiler's fallback places an event by calling
        ``latlon_to_pgid`` on its coordinates. If a planted cell did
        not round-trip, a guard asserting "the declared cell won, not
        the coordinates" could pass for the wrong reason.
        """
        cells = (*_GEN.GAUL1_POLYGON_A, *_GEN.GAUL1_POLYGON_B)
        for pgid in cells:
            lat, lon = _GEN._centroid(pgid)
            back = latlon_to_pgid(
                np.array([lat]), np.array([lon]), DEFAULT_GRID_CONFIG,
            )
            assert int(back[0]) == pgid


class TestSyntheticUcdpEventsGreen:
    """The event parquet must satisfy both weight-map builders."""

    def test_columns_cover_what_the_weight_maps_require(
        self, fixtures: dict,
    ) -> None:
        names = set(pq.read_table(fixtures["events_path"]).column_names)
        spatial_required = {
            "where_prec", "priogrid_gid", "best",
        }
        temporal_required = {
            "best", "date_start", "date_prec", "where_prec",
            *CASCADE_KEYS,
        }
        missing = (spatial_required | temporal_required) - names
        assert not missing, f"event parquet lacks {sorted(missing)}"

    def test_all_four_precision_classes_are_present(
        self, fixtures: dict,
    ) -> None:
        """A precise seed plus admin-1, month-imprecise, and country.

        Without the precise events there is no well-located mass, and
        ``proportional`` falls through to the uniform branch -- which
        would make a passing allocation test say nothing about
        proportionality.
        """
        precisions = {r["where_prec"] for r in fixtures["rows"]}
        assert {1, 4, 5, 6} <= precisions, sorted(precisions)

    def test_imprecise_events_sit_at_the_source_cell(
        self, fixtures: dict,
    ) -> None:
        """Their coordinates must name the cell they came from.

        This is the condition that makes the delivery guards
        meaningful: the allocated cells differ from the cell the
        coordinates resolve to, so coordinate placement and declared
        placement cannot be confused.
        """
        for event_id in (
            _GEN.ADMIN1_EVENT_ID,
            _GEN.SUMMARY_EVENT_ID,
            _GEN.COUNTRY_EVENT_ID,
        ):
            row = _event(fixtures["rows"], event_id)
            assert row["priogrid_gid"] == _GEN.SUMMARY_EVENT_PGID
            back = latlon_to_pgid(
                np.array([row["latitude"]]),
                np.array([row["longitude"]]),
                DEFAULT_GRID_CONFIG,
            )
            assert int(back[0]) == _GEN.SUMMARY_EVENT_PGID

    def test_the_temporal_pool_is_not_empty(
        self, fixtures: dict,
    ) -> None:
        """Else every temporal allocation falls through to uniform."""
        table = pq.read_table(fixtures["events_path"])
        weights = build_temporal_weight_map(table)
        assert weights.n_pool_events == len(
            _GEN.WELL_LOCATED_FATALITIES
        )


class TestTheAllocatorRunsOnSyntheticFixturesGreen:
    """The production allocator, on invented geography."""

    def test_the_weight_map_builds(self, fixtures: dict) -> None:
        table = pq.read_table(fixtures["events_path"])
        weights = build_spatial_weight_map(
            table, fixtures["gaul1"], fixtures["gaul0"],
        )
        assert weights.admin1_weights[_GEN.GAUL1_CODE_A]
        assert weights.country_weights[_GEN.GAUL0_CODE]

    def test_the_summary_event_spreads_over_several_cells(
        self, fixtures: dict,
    ) -> None:
        """Issue #550's acceptance criterion, stated directly."""
        table = pq.read_table(fixtures["events_path"])
        weights = build_spatial_weight_map(
            table, fixtures["gaul1"], fixtures["gaul0"],
        )
        rows = get_spatial_distribution("proportional")(
            _event(fixtures["rows"], _GEN.SUMMARY_EVENT_ID), weights,
        )
        assert len(rows) > 1, (
            "the where_prec=5 event was not distributed, so no "
            "delivery guard built on this fixture could mean anything"
        )
        cells = tuple(sorted({r["priogrid_gid"] for r in rows}))
        assert cells == _GEN.ADMIN1_ALLOCATION_CELLS, (
            f"allocated {cells}, planted "
            f"{_GEN.ADMIN1_ALLOCATION_CELLS}"
        )

    def test_allocation_conserves_the_event_total(
        self, fixtures: dict,
    ) -> None:
        table = pq.read_table(fixtures["events_path"])
        weights = build_spatial_weight_map(
            table, fixtures["gaul1"], fixtures["gaul0"],
        )
        event = _event(fixtures["rows"], _GEN.SUMMARY_EVENT_ID)
        rows = get_spatial_distribution("proportional")(event, weights)
        assert sum(r["best"] for r in rows) == _GEN.SUMMARY_EVENT_BEST

    def test_country_allocation_reaches_further_than_admin1(
        self, fixtures: dict,
    ) -> None:
        """A where_prec=6 event must cross the polygon boundary.

        Both imprecise events name the same source cell, so if the
        fixture could not tell admin-1 from country placement, a test
        asserting the correct level would pass either way.
        """
        table = pq.read_table(fixtures["events_path"])
        weights = build_spatial_weight_map(
            table, fixtures["gaul1"], fixtures["gaul0"],
        )
        rows = get_spatial_distribution("proportional")(
            _event(fixtures["rows"], _GEN.COUNTRY_EVENT_ID), weights,
        )
        cells = tuple(sorted({r["priogrid_gid"] for r in rows}))
        assert cells == _GEN.COUNTRY_ALLOCATION_CELLS
        assert set(_GEN.ADMIN1_ALLOCATION_CELLS) < set(cells), (
            "country placement did not reach beyond admin-1"
        )


class TestFixturesNeedNoRealDataRed:
    """The whole point of the story, as a guard.

    Every path in this repository that reaches for GAUL data does so
    with a *relative* path -- ``data/raw/gaul_admin/...``. Running the
    chain from a working directory that contains no ``data/`` therefore
    makes any such read fail rather than silently succeed off the
    developer's machine.

    If someone later repairs a failing fixture by pointing it back at
    the real crosswalks, this test is what goes red.
    """

    def test_the_chain_runs_from_a_directory_with_no_data_tree(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        work = tmp_path / "elsewhere"
        work.mkdir()
        monkeypatch.chdir(work)
        assert not (Path.cwd() / "data").exists(), (
            "premise guard: this directory must have no data/ tree"
        )

        gaul = _GEN.write_synthetic_gaul(work / "gaul_admin")
        events_path = work / "events.parquet"
        rows = _GEN.write_synthetic_ucdp_events(events_path)
        table = pq.read_table(events_path)

        weights = build_spatial_weight_map(
            table, gaul["gaul1_code"], gaul["gaul0_code"],
        )
        allocated = get_spatial_distribution("proportional")(
            _event(rows, _GEN.SUMMARY_EVENT_ID), weights,
        )
        assert len(allocated) > 1
