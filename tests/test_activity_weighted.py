"""Activity-weighted temporal allocation (option T2).

The difference from ``uniform_span`` is only the weights: each month in
the span is weighted by fatalities that *well-observed* events in the same
conflict recorded in that month, instead of ``1/m``.

Measured before it was built, on 20,000 events whose true month is known
and with each event removed from its own indicator
(``scripts/evaluate_temporal_allocation.py``): mean distance from the true
month 4.883 -> 3.305 months, mean hit share 0.0825 -> 0.1525, closer than
uniform on 64.9% of events. These tests pin the mechanism; that script is
what would falsify the choice.
"""

from __future__ import annotations

from datafactory_viewpoint.temporal_distribution import (
    activity_weighted,
    get_distribution,
    uniform_span,
)
from datafactory_viewpoint.temporal_weights import TemporalWeightMap

#: month_id for 2021-01 .. 2021-12 (month_id = (year-1980)*12 + month)
JAN_2021 = (2021 - 1980) * 12 + 1

EVENT = {
    "id": 463131,
    "best": 1200,
    "low": 1200,
    "high": 1200,
    "date_prec": 5,
    "date_start": "2021-01-01",
    "date_end": "2021-12-31",
    "dyad_new_id": 777,
    "conflict_new_id": 555,
    "side_b_new_id": 333,
    "country_id": 111,
}


def _map(**levels: dict[tuple[int, int], float]) -> TemporalWeightMap:
    base: dict[str, dict[tuple[int, int], float]] = {
        "dyad_new_id": {},
        "conflict_new_id": {},
        "side_b_new_id": {},
        "country_id": {},
    }
    base.update(levels)
    return TemporalWeightMap(activity=base, n_pool_events=0)


class TestFallbacks:
    """Never fall back to the behaviour being replaced."""

    def test_no_weight_map_falls_back_to_uniform(self) -> None:
        assert activity_weighted(EVENT, None) == uniform_span(EVENT)

    def test_no_activity_at_any_level_falls_back_to_uniform(self) -> None:
        assert activity_weighted(EVENT, _map()) == uniform_span(EVENT)

    def test_fallback_is_uniform_not_endpoint(self) -> None:
        """The whole point is not to dump everything on date_end."""
        rows = activity_weighted(EVENT, _map())
        assert len(rows) == 12, (
            "falling back to date_end_only would reintroduce the defect"
        )


class TestActivityDrivesTheAllocation:
    def test_all_activity_in_one_month_concentrates_there(self) -> None:
        wm = _map(dyad_new_id={(777, JAN_2021 + 5): 50.0})
        rows = activity_weighted(EVENT, wm)
        assert len(rows) == 1
        assert rows[0]["date_month"] == "2021-06-01"
        assert rows[0]["best"] == 1200

    def test_two_active_months_split_by_their_weights(self) -> None:
        wm = _map(dyad_new_id={
            (777, JAN_2021 + 0): 75.0,
            (777, JAN_2021 + 1): 25.0,
        })
        rows = activity_weighted(EVENT, wm)
        by_month = {r["date_month"]: r["best"] for r in rows}
        assert by_month == {"2021-01-01": 900, "2021-02-01": 300}

    def test_zero_activity_months_receive_nothing(self) -> None:
        """Zero weight means zero allocation -- the rounder guarantees it.

        This is the assumption most likely to be wrong, and it is
        deliberate: absence of well-located reporting is not absence of
        fighting. Pinned so that changing it has to be a decision.
        """
        wm = _map(dyad_new_id={
            (777, JAN_2021 + 0): 1.0,
            (777, JAN_2021 + 11): 1.0,
        })
        rows = activity_weighted(EVENT, wm)
        assert {r["date_month"] for r in rows} == {
            "2021-01-01", "2021-12-01",
        }


class TestTheCascade:
    """Most specific level with nonzero activity wins."""

    def test_dyad_preferred_over_conflict(self) -> None:
        wm = _map(
            dyad_new_id={(777, JAN_2021 + 2): 10.0},
            conflict_new_id={(555, JAN_2021 + 8): 999.0},
        )
        rows = activity_weighted(EVENT, wm)
        assert [r["date_month"] for r in rows] == ["2021-03-01"]
        assert rows[0]["_temporal_weight_key"] == "dyad_new_id"

    def test_falls_through_to_conflict(self) -> None:
        wm = _map(conflict_new_id={(555, JAN_2021 + 8): 5.0})
        rows = activity_weighted(EVENT, wm)
        assert rows[0]["_temporal_weight_key"] == "conflict_new_id"

    def test_falls_through_to_side_b(self) -> None:
        wm = _map(side_b_new_id={(333, JAN_2021 + 3): 5.0})
        rows = activity_weighted(EVENT, wm)
        assert rows[0]["_temporal_weight_key"] == "side_b_new_id"

    def test_falls_through_to_country(self) -> None:
        wm = _map(country_id={(111, JAN_2021 + 4): 5.0})
        rows = activity_weighted(EVENT, wm)
        assert rows[0]["_temporal_weight_key"] == "country_id"


class TestConservationAndTrigger:
    def test_conserves_every_extensive_field(self) -> None:
        wm = _map(dyad_new_id={
            (777, JAN_2021 + i): float(i + 1) for i in range(12)
        })
        event = {**EVENT, "best": 1201, "low": 7, "high": 99_999}
        rows = activity_weighted(event, wm)
        for field in ("best", "low", "high"):
            assert sum(r[field] for r in rows) == event[field]

    def test_precise_date_is_not_allocated(self) -> None:
        wm = _map(dyad_new_id={(777, JAN_2021 + 5): 50.0})
        event = {**EVENT, "date_prec": 1}
        rows = activity_weighted(event, wm)
        assert len(rows) == 1
        assert rows[0]["date_month"] == "2021-12-01"
        assert "_temporal_distributed" not in rows[0]

    def test_single_month_span_is_not_allocated(self) -> None:
        wm = _map(dyad_new_id={(777, JAN_2021 + 5): 50.0})
        event = {**EVENT, "date_start": "2021-06-02",
                 "date_end": "2021-06-29"}
        rows = activity_weighted(event, wm)
        assert len(rows) == 1
        assert rows[0]["best"] == EVENT["best"]

    def test_registered_under_its_name(self) -> None:
        assert get_distribution("activity_weighted") is activity_weighted
