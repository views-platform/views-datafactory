"""Guards for ``scripts/verify_source_parity.py``.

The script answers the one question nothing else here asks: does
what we serve equal what UCDP published? These tests exercise its
arithmetic on a synthetic consolidated store, so they need neither
``data/`` nor the network and run in CI.

What is deliberately *not* tested here is ``served_totals``, which
reads the real grid through ``load_dataset``. A fixture asserting
that invented cells sum to the invented total would be mutation
category M4 — conformance to a declaration nothing checks. The
parity run itself is the exerciser for that half, and it runs in
the pipeline rather than in CI.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest


def _load_module():  # type: ignore[no-untyped-def]
    sys.path.insert(0, str(Path("scripts")))
    try:
        import verify_source_parity  # noqa: PLC0415

        return verify_source_parity
    finally:
        sys.path.pop(0)


def _store(path: Path, rows: list[dict]) -> Path:
    """A consolidated store holding exactly the rows given."""
    table = pa.table({
        "id": pa.array([r["id"] for r in rows], pa.int64()),
        "best": pa.array([r["best"] for r in rows], pa.int64()),
        "year": pa.array([r["year"] for r in rows], pa.int64()),
        "type_of_violence": pa.array(
            [r["tov"] for r in rows], pa.int64()),
        "_source_type": pa.array([r["stype"] for r in rows], pa.string()),
        "_source_version": pa.array([r["sver"] for r in rows], pa.string()),
        "_ingested_at": pa.array(
            [r.get("at", "2026-01-01T00:00:00") for r in rows], pa.string()),
    })
    pq.write_table(table, path)
    return path


# ── version selection ───────────────────────────────────────


class TestLatestAnnualVersion:
    """The release compared against must be the newest one present."""

    def test_numeric_not_lexicographic(self, tmp_path: Path) -> None:
        """25.11 must not outrank 26.1, which is what text sort gives.

        This is the bug the comparison exists to avoid: as strings,
        "25.11" > "26.1" is False but "9.1" > "26.1" is True, and a
        store that has seen a single-digit version would silently
        compare against it.
        """
        mod = _load_module()
        store = _store(tmp_path / "s.parquet", [
            {"id": 1, "best": 10, "year": 2023, "tov": 1,
             "stype": "annual", "sver": "25.11"},
            {"id": 2, "best": 20, "year": 2023, "tov": 1,
             "stype": "annual", "sver": "26.1"},
            {"id": 3, "best": 30, "year": 2023, "tov": 1,
             "stype": "annual", "sver": "9.1"},
        ])
        assert mod.latest_annual_version(store) == "26.1"

    def test_no_annual_release_is_refused_not_guessed(
        self, tmp_path: Path,
    ) -> None:
        """A store with only .9 cannot answer; it must say so.

        Falling back to .9 would compare the pipeline against its own
        input, which is exactly the class of check that let the
        withdrawn-event defect run for four and a half months.
        """
        mod = _load_module()
        store = _store(tmp_path / "s.parquet", [
            {"id": 1, "best": 10, "year": 2023, "tov": 1,
             "stype": "dot9", "sver": "26.9.1"},
        ])
        with pytest.raises(SystemExit):
            mod.latest_annual_version(store)


# ── the two totals ──────────────────────────────────────────


class TestTotals:
    """Published mass and .9-exclusive mass, split by year and type."""

    def test_published_totals_exclude_other_versions_and_types(
        self, tmp_path: Path,
    ) -> None:
        mod = _load_module()
        store = _store(tmp_path / "s.parquet", [
            {"id": 1, "best": 100, "year": 2023, "tov": 1,
             "stype": "annual", "sver": "26.1"},
            {"id": 2, "best": 7, "year": 2023, "tov": 3,
             "stype": "annual", "sver": "26.1"},
            {"id": 3, "best": 999, "year": 2023, "tov": 1,
             "stype": "annual", "sver": "25.1"},   # superseded
            {"id": 4, "best": 500, "year": 2023, "tov": 1,
             "stype": "dot9", "sver": "26.9.1"},   # not the release
        ])
        totals = mod.source_totals(store, "26.1")
        assert totals == {(2023, 1): 100.0, (2023, 3): 7.0}

    def test_one_release_in_two_harvest_vintages_counts_once(
        self, tmp_path: Path,
    ) -> None:
        """ADR-017's re-fetch, measured in the real store and missed once.

        On 2026-11-22 annual 25.1 held 769,836 rows for 384,918
        distinct ids -- each exactly twice, harvested 2026-03-23 and
        2026-05-21. Summing the rows as they lay doubled every
        published figure, and the first end-to-end run of this check
        reported 108 of 108 totals as failures against a store that
        was fine. The later vintage wins.
        """
        mod = _load_module()
        store = _store(tmp_path / "s.parquet", [
            {"id": 1, "best": 100, "year": 2023, "tov": 1,
             "stype": "annual", "sver": "26.1", "at": "2026-03-23T11:13:05"},
            {"id": 1, "best": 110, "year": 2023, "tov": 1,
             "stype": "annual", "sver": "26.1", "at": "2026-05-21T00:20:37"},
            {"id": 2, "best": 5, "year": 2023, "tov": 1,
             "stype": "annual", "sver": "26.1", "at": "2026-03-23T11:13:05"},
        ])
        # 110 (the later vintage of id 1, not 100 and not 210) + 5
        assert mod.source_totals(store, "26.1") == {(2023, 1): 115.0}

    def test_dot9_vintages_also_count_once(self, tmp_path: Path) -> None:
        """The same duplication on the .9 side inflates the term that
        *explains* a difference, which is worse than inflating the
        difference itself -- it hides a real one."""
        mod = _load_module()
        store = _store(tmp_path / "s.parquet", [
            {"id": 1, "best": 100, "year": 2023, "tov": 1,
             "stype": "annual", "sver": "26.1"},
            {"id": 9, "best": 13, "year": 2023, "tov": 1,
             "stype": "dot9", "sver": "26.9.2", "at": "2026-03-23T11:13:05"},
            {"id": 9, "best": 13, "year": 2023, "tov": 1,
             "stype": "dot9", "sver": "26.9.2", "at": "2026-05-21T00:20:37"},
        ])
        assert mod.dot9_exclusive_totals(store, "26.1") == {(2023, 1): 13.0}

    def test_dot9_exclusive_counts_only_ids_absent_from_the_release(
        self, tmp_path: Path,
    ) -> None:
        """ADR-015's exclusive events, and nothing already published.

        Double-counting an id present in both would manufacture the
        exact positive difference this script exists to detect.
        """
        mod = _load_module()
        store = _store(tmp_path / "s.parquet", [
            {"id": 1, "best": 100, "year": 2023, "tov": 1,
             "stype": "annual", "sver": "26.1"},
            {"id": 1, "best": 100, "year": 2023, "tov": 1,
             "stype": "dot9", "sver": "26.9.2"},   # same id — not exclusive
            {"id": 2, "best": 13, "year": 2023, "tov": 1,
             "stype": "dot9", "sver": "26.9.2"},   # exclusive
            {"id": 3, "best": 777, "year": 2023, "tov": 1,
             "stype": "dot9", "sver": "26.9.1"},   # not the newest .9
        ])
        assert mod.dot9_exclusive_totals(store, "26.1") == {(2023, 1): 13.0}


# ── the comparison ──────────────────────────────────────────


class TestCompare:
    """The remainder, and which remainders are findings."""

    def test_exclusive_mass_explains_a_positive_difference(self) -> None:
        mod = _load_module()
        rows = mod.compare(
            served={(2023, 1): 113.0},
            source={(2023, 1): 100.0},
            exclusive={(2023, 1): 13.0},
            tolerance=0.0,
        )
        assert rows[0]["unexplained"] == 0.0
        assert rows[0]["ok"] is True

    def test_serving_more_than_published_is_a_finding(self) -> None:
        """The withdrawn-event defect's own signature."""
        mod = _load_module()
        rows = mod.compare(
            served={(2023, 1): 2878.0},
            source={(2023, 1): 0.0},
            exclusive={},
            tolerance=0.0,
        )
        assert rows[0]["unexplained"] == 2878.0
        assert rows[0]["ok"] is False

    def test_serving_less_than_published_is_a_finding(self) -> None:
        """A short harvest or a filter nobody meant to apply."""
        mod = _load_module()
        rows = mod.compare(
            served={(2023, 1): 90.0},
            source={(2023, 1): 100.0},
            exclusive={},
            tolerance=0.0,
        )
        assert rows[0]["unexplained"] == -10.0
        assert rows[0]["ok"] is False

    def test_a_year_served_but_never_published_is_not_silently_dropped(
        self,
    ) -> None:
        """Keys are the union, so a year on one side only still appears."""
        mod = _load_module()
        rows = mod.compare(
            served={(2024, 1): 50.0},
            source={(2023, 1): 100.0},
            exclusive={},
            tolerance=0.0,
        )
        years = {(r["year"], r["type_of_violence"]) for r in rows}
        assert years == {(2023, 1), (2024, 1)}
        assert [r for r in rows if r["year"] == 2024][0]["ok"] is False

    def test_an_undelivered_violence_type_is_a_finding_not_a_drop(
        self,
    ) -> None:
        """``type_of_violence`` 4 has no ``ged_*`` feature.

        It must surface as an unexplained difference rather than be
        quietly excluded, which is how a whole class of events would
        go missing without anything saying so.
        """
        mod = _load_module()
        rows = mod.compare(
            served={}, source={(2023, 4): 42.0},
            exclusive={}, tolerance=0.0,
        )
        assert rows[0]["feature"] == "<tov 4>"
        assert rows[0]["unexplained"] == -42.0
        assert rows[0]["ok"] is False

    def test_tolerance_is_absolute_deaths_and_symmetric(self) -> None:
        mod = _load_module()
        for served in (105.0, 95.0):
            rows = mod.compare(
                served={(2023, 1): served}, source={(2023, 1): 100.0},
                exclusive={}, tolerance=5.0,
            )
            assert rows[0]["ok"] is True
        rows = mod.compare(
            served={(2023, 1): 106.0}, source={(2023, 1): 100.0},
            exclusive={}, tolerance=5.0,
        )
        assert rows[0]["ok"] is False


# ── the year/month mapping ──────────────────────────────────


class TestMonthsOf:
    """month_id 1 is 1980-01. Off by one here moves every total."""

    @pytest.mark.parametrize(
        ("year", "expected"),
        [(1980, (1, 12)), (1989, (109, 120)),
         (2022, (505, 516)), (2024, (529, 540))],
    )
    def test_known_year_boundaries(
        self, year: int, expected: tuple[int, int],
    ) -> None:
        mod = _load_module()
        assert mod.months_of(year) == expected

    def test_years_tile_without_gap_or_overlap(self) -> None:
        mod = _load_module()
        for year in range(1989, 2027):
            assert mod.months_of(year)[1] + 1 == mod.months_of(year + 1)[0]
