"""Characterization: event_validation direct tests (C-269, #196).

Pin validate_events() and compare_snapshots() behavior to catch
regressions during refactoring. Source module is NOT modified.
"""

from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from datafactory_harvester.event_validation import (
    ComparisonResult,
    ValidationResult,
    compare_snapshots,
    validate_events,
)

# ---- Fixtures ----

REQUIRED: set[str] = {
    "id", "country_id", "country", "date_start",
    "best", "high", "low", "type_of_violence",
}

FIELD_TYPES: dict[str, tuple[type, ...]] = {
    "id": (int,),
    "country_id": (int,),
    "best": (int, float),
}


def _make_events(n: int = 3, id_start: int = 1) -> list[dict]:
    return [
        {
            "id": i,
            "country_id": 100 + i,
            "country": f"Country{i}",
            "date_start": f"2024-01-{i:02d}",
            "best": i * 10,
            "high": i * 15,
            "low": i * 5,
            "type_of_violence": 1,
        }
        for i in range(id_start, id_start + n)
    ]


def _write_parquet(events: list[dict], path: Path) -> None:
    table = pa.table({k: [e[k] for e in events] for k in events[0]})
    pq.write_table(table, path)


# ---------------------------------------------------------------------------
# TestValidateEventsCharacterization
# ---------------------------------------------------------------------------


class TestValidateEventsCharacterization:

    def test_valid_list_returns_zero_errors(self) -> None:
        result = validate_events(_make_events(), REQUIRED, FIELD_TYPES)
        assert isinstance(result, ValidationResult)
        assert result.valid is True
        assert len(result.errors) == 0
        assert result.n_events == 3

    def test_missing_required_column_returns_error(self) -> None:
        events = _make_events()
        for ev in events:
            del ev["best"]
        result = validate_events(events, REQUIRED, FIELD_TYPES)
        assert result.valid is False
        assert len(result.errors) > 0
        assert any("best" in err for err in result.errors)

    def test_null_in_non_nullable_column_returns_warning(
        self,
    ) -> None:
        events = _make_events()
        events[0]["best"] = None
        result = validate_events(events, REQUIRED, FIELD_TYPES)
        assert result.valid is True
        assert result.n_events == 3

    def test_empty_list_returns_invalid(self) -> None:
        result = validate_events([], REQUIRED, FIELD_TYPES)
        assert result.valid is False
        assert result.n_events == 0
        assert any(
            "No events to validate" in err for err in result.errors
        )


# ---------------------------------------------------------------------------
# TestCompareSnapshotsCharacterization
# ---------------------------------------------------------------------------


class TestCompareSnapshotsCharacterization:

    def test_identical_snapshots_show_zero_changes(
        self, tmp_path: Path,
    ) -> None:
        events = _make_events(5)
        old_path = tmp_path / "old.parquet"
        _write_parquet(events, old_path)

        result = compare_snapshots(old_path, events)
        assert isinstance(result, ComparisonResult)
        assert result.has_previous is True
        assert result.n_added == 0
        assert result.n_removed == 0
        assert result.n_revised == 0

    def test_added_rows_detected(self, tmp_path: Path) -> None:
        old_events = _make_events(3)
        new_events = _make_events(5)
        old_path = tmp_path / "old.parquet"
        _write_parquet(old_events, old_path)

        result = compare_snapshots(old_path, new_events)
        assert result.n_added == 2

    def test_removed_rows_detected(self, tmp_path: Path) -> None:
        old_events = _make_events(5)
        new_events = _make_events(3)
        old_path = tmp_path / "old.parquet"
        _write_parquet(old_events, old_path)

        result = compare_snapshots(old_path, new_events)
        assert result.n_removed == 2

    def test_revised_rows_detected(self, tmp_path: Path) -> None:
        old_events = _make_events(3)
        new_events = _make_events(3)
        new_events[1]["best"] = 999

        old_path = tmp_path / "old.parquet"
        _write_parquet(old_events, old_path)

        result = compare_snapshots(old_path, new_events)
        assert result.n_revised == 1
        assert result.total_revision_magnitude > 0
