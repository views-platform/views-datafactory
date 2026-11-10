"""The declared-trigger conserving temporal allocator (option T1).

Specified in section 4 of
``reports/2026-11-04_summary_event_allocation_dossier/11_allocator_spec.md``.

``uniform_span`` is the temporal counterpart of ADR-049's spatial work and
the floor any weighted temporal strategy must beat. Three things separate
it from the strategies already in this module:

1. **It triggers on UCDP's declaration** (``date_prec >= 4`` *and* a span
   crossing a month boundary), not on span-and-magnitude. ``ceil_split``
   never consults ``date_prec``.
2. **It cannot inflate**, because allocation goes through the shared
   largest-remainder rounder. ``ceil_split``'s measured excess across the
   consolidated store is 0.91%.
3. **It emits only nonzero rows**, so output is bounded by
   ``min(value, span)`` rather than by ``span``.
"""

from __future__ import annotations

import pytest

from datafactory_viewpoint.temporal_distribution import (
    ceil_split,
    get_distribution,
    uniform_span,
)

#: The Tigray war's annual aggregate -- the event in views-datafactory#533.
TIGRAY = {
    "id": 463131,
    "best": 113_368,
    "low": 100_000,
    "high": 120_000,
    "date_prec": 5,
    "where_prec": 5,
    "date_start": "2021-01-01",
    "date_end": "2021-12-31",
    "priogrid_gid": 148759,
}


class TestConservation:
    """ADR-040 Invariant 1, on each extensive field independently."""

    def test_the_tigray_event(self) -> None:
        rows = uniform_span(TIGRAY)
        assert len(rows) == 12, "a whole year should reach all twelve months"
        for field in ("best", "low", "high"):
            assert sum(r[field] for r in rows) == TIGRAY[field], (
                f"{field} not conserved"
            )

    @pytest.mark.parametrize("value", [0, 1, 2, 11, 12, 13, 99, 100_003])
    def test_across_magnitudes(self, value: int) -> None:
        event = {**TIGRAY, "best": value, "low": value, "high": value}
        rows = uniform_span(event)
        assert sum(r["best"] for r in rows) == value

    def test_no_inflation_where_ceil_split_inflates(self) -> None:
        """The defect this replaces, shown side by side.

        ``ceil_split`` assigns ``ceil(7/3) = 3`` to each of three months
        and so emits 9 against an input of 7.
        """
        event = {
            "best": 7, "low": 7, "high": 7, "date_prec": 5,
            "date_start": "2021-01-01", "date_end": "2021-03-31",
        }
        assert sum(r["best"] for r in ceil_split(event)) == 9, (
            "ceil_split is expected to inflate; if this changed, the "
            "comparison below is no longer the point"
        )
        assert sum(r["best"] for r in uniform_span(event)) == 7


class TestTheDeclaredTrigger:
    """Both conditions are required, and each for its own reason."""

    def test_date_prec_5_spanning_months_is_allocated(self) -> None:
        assert len(uniform_span(TIGRAY)) == 12

    def test_date_prec_4_spanning_months_is_allocated(self) -> None:
        """4 is "month known, day unknown" -- ambiguous across a boundary."""
        event = {**TIGRAY, "date_prec": 4,
                 "date_start": "2021-01-28", "date_end": "2021-02-03"}
        assert len(uniform_span(event)) == 2

    def test_precise_date_spanning_months_is_not_allocated(self) -> None:
        """A precisely dated event straddling a calendar boundary.

        Not imprecise -- a different problem with a different answer. It
        must land on one month, as ``date_end_only`` would place it.
        """
        event = {**TIGRAY, "date_prec": 1,
                 "date_start": "2021-01-30", "date_end": "2021-02-02"}
        rows = uniform_span(event)
        assert len(rows) == 1
        assert rows[0]["date_month"] == "2021-02-01"
        assert rows[0]["best"] == TIGRAY["best"]

    def test_imprecise_but_single_month_is_not_allocated(self) -> None:
        """Nothing to allocate; the month is already right."""
        event = {**TIGRAY, "date_prec": 5,
                 "date_start": "2021-06-02", "date_end": "2021-06-29"}
        rows = uniform_span(event)
        assert len(rows) == 1
        assert rows[0]["best"] == TIGRAY["best"]


class TestTheSparseRegime:
    """value < span: allocation selects months rather than spreading."""

    def test_one_death_over_twelve_months_stays_one_death(self) -> None:
        event = {**TIGRAY, "best": 1, "low": 1, "high": 1}
        rows = uniform_span(event)
        assert sum(r["best"] for r in rows) == 1
        assert len(rows) == 1, (
            "only the month that received the death should be emitted"
        )

    def test_row_count_is_bounded_by_value(self) -> None:
        for value in (1, 3, 5):
            event = {**TIGRAY, "best": value, "low": 0, "high": 0}
            rows = uniform_span(event)
            assert len(rows) <= value

    def test_zero_valued_event_still_produces_a_row(self) -> None:
        """A zero event happened; dropping it would break accountability."""
        event = {**TIGRAY, "best": 0, "low": 0, "high": 0}
        rows = uniform_span(event)
        assert len(rows) == 1
        assert rows[0]["best"] == 0
        assert rows[0]["date_month"] == "2021-12-01"


class TestProvenanceAndRegistration:
    def test_registered_under_its_name(self) -> None:
        assert get_distribution("uniform_span") is uniform_span

    def test_allocated_rows_are_marked(self) -> None:
        rows = uniform_span(TIGRAY)
        assert all(r["_temporal_distributed"] for r in rows)
        assert all(r["_temporal_n_months"] == 12 for r in rows)

    def test_untouched_rows_are_not_marked(self) -> None:
        event = {**TIGRAY, "date_prec": 1}
        rows = uniform_span(event)
        assert "_temporal_distributed" not in rows[0]

    def test_original_fields_survive(self) -> None:
        rows = uniform_span(TIGRAY)
        assert all(r["id"] == 463131 for r in rows)
        assert all(r["priogrid_gid"] == 148759 for r in rows)
        assert all(r["where_prec"] == 5 for r in rows)
