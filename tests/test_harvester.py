"""Tests for datafactory_harvester shared skeleton.

Covers ValidationResult, ComparisonResult, validate_events,
compare_snapshots, save_event_snapshot, archive_snapshot,
and the source registry.
"""

from __future__ import annotations

from pathlib import Path

import pyarrow.parquet as pq
import pytest

from datafactory_harvester import (
    compare_snapshots,
    save_event_snapshot,
    validate_events,
)

# ---- Helpers ----


def _make_events(n: int = 3) -> list[dict]:
    """Create minimal valid UCDP-like events."""
    return [
        {
            "id": i,
            "country_id": 100 + i,
            "country": f"Country{i}",
            "date_start": f"2024-01-{i + 1:02d}",
            "best": i * 10,
            "high": i * 15,
            "low": i * 5,
            "type_of_violence": 1,
            "event_clarity": 1,
            "code_status": "Clear",
            "where_prec": 1,
            "date_prec": 1,
            "number_of_sources": 2,
        }
        for i in range(1, n + 1)
    ]


REQUIRED = {
    "id", "country_id", "country", "date_start",
    "best", "high", "low", "type_of_violence",
}

FIELD_TYPES: dict[str, tuple[type, ...]] = {
    "id": (int,),
    "country_id": (int,),
    "best": (int, float),
}


# ---- ValidationResult ----


class TestValidationResultGreen:

    def test_valid_events(self) -> None:
        result = validate_events(_make_events(), REQUIRED, FIELD_TYPES)
        assert result.valid
        assert result.n_events == 3
        assert len(result.errors) == 0

    def test_content_digest_is_16_char_hex(self) -> None:
        result = validate_events(_make_events(), REQUIRED, FIELD_TYPES)
        assert len(result.content_digest) == 16
        assert all(c in "0123456789abcdef" for c in result.content_digest)

    def test_content_digest_deterministic(self) -> None:
        events = _make_events()
        a = validate_events(events, REQUIRED, FIELD_TYPES)
        b = validate_events(events, REQUIRED, FIELD_TYPES)
        assert a.content_digest == b.content_digest

    def test_schema_snapshot_captured(self) -> None:
        result = validate_events(_make_events(), REQUIRED, FIELD_TYPES)
        assert "id" in result.schema_snapshot
        assert result.schema_snapshot["id"] == "int"


class TestValidateEventsBeige:

    def test_empty_events(self) -> None:
        result = validate_events([], REQUIRED, FIELD_TYPES)
        assert not result.valid
        assert "No events" in result.errors[0]

    def test_missing_required_field(self) -> None:
        events = [{"id": 1, "country_id": 100}]  # Missing many required
        result = validate_events(events, REQUIRED, FIELD_TYPES)
        assert not result.valid
        assert any("missing" in e.lower() for e in result.errors)

    def test_wrong_type_recorded_as_error(self) -> None:
        events = _make_events(1)
        events[0]["id"] = "not_an_int"
        result = validate_events(events, REQUIRED, FIELD_TYPES)
        assert not result.valid
        assert any("id" in e and "str" in e for e in result.errors)

    def test_duplicate_ids_warning(self) -> None:
        events = _make_events(2)
        events[1]["id"] = events[0]["id"]  # Duplicate
        result = validate_events(events, REQUIRED, FIELD_TYPES)
        assert any("Duplicate" in w for w in result.warnings)

    def test_negative_best_warning(self) -> None:
        events = _make_events(1)
        events[0]["best"] = -5
        events[0]["low"] = -10
        result = validate_events(events, REQUIRED, FIELD_TYPES)
        assert any("Negative" in w for w in result.warnings)

    def test_bound_violation_warning(self) -> None:
        events = _make_events(1)
        events[0]["best"] = 100
        events[0]["high"] = 50  # best > high
        result = validate_events(events, REQUIRED, FIELD_TYPES)
        assert any("bound" in w.lower() for w in result.warnings)


class TestValidateEventsRed:
    """Adversarial inputs — garbage from a broken API."""

    def test_all_none_fields_does_not_crash(self) -> None:
        events = [dict.fromkeys(REQUIRED)]
        result = validate_events(events, REQUIRED, FIELD_TYPES)
        # All fields present but None — type checks skip None values,
        # so result is valid but content digest covers None values
        assert result.n_events == 1
        assert result.content_digest != ""

    def test_empty_dicts_detected_as_missing(self) -> None:
        result = validate_events([{}], REQUIRED, FIELD_TYPES)
        assert not result.valid
        assert any("missing" in e.lower() for e in result.errors)

    def test_wrong_type_on_every_field(self) -> None:
        events = [{k: [] for k in REQUIRED}]  # lists, not ints/strs
        result = validate_events(events, REQUIRED, FIELD_TYPES)
        assert not result.valid

    def test_none_id_in_digest(self) -> None:
        events = _make_events(1)
        events[0]["id"] = None
        # Should not raise during digest computation
        result = validate_events(events, REQUIRED, FIELD_TYPES)
        assert len(result.content_digest) == 16


# ---- ComparisonResult ----


class TestCompareSnapshotsGreen:

    def test_no_previous_snapshot(self, tmp_path: Path) -> None:
        result = compare_snapshots(
            tmp_path / "nonexistent.parquet", _make_events()
        )
        assert not result.has_previous

    def test_identical_snapshots(self, tmp_path: Path) -> None:
        events = _make_events()
        snap = tmp_path / "old.parquet"
        save_event_snapshot(events, snap)
        result = compare_snapshots(snap, events)
        assert result.has_previous
        assert result.n_added == 0
        assert result.n_removed == 0
        assert result.n_revised == 0

    def test_detects_added_events(self, tmp_path: Path) -> None:
        old_events = _make_events(2)
        new_events = _make_events(3)
        snap = tmp_path / "old.parquet"
        save_event_snapshot(old_events, snap)
        result = compare_snapshots(snap, new_events)
        assert result.n_added == 1

    def test_detects_removed_events(self, tmp_path: Path) -> None:
        old_events = _make_events(3)
        new_events = _make_events(2)
        snap = tmp_path / "old.parquet"
        save_event_snapshot(old_events, snap)
        result = compare_snapshots(snap, new_events)
        assert result.n_removed == 1

    def test_detects_revised_events(self, tmp_path: Path) -> None:
        old_events = _make_events(2)
        new_events = _make_events(2)
        new_events[0]["best"] = 999  # Revise
        snap = tmp_path / "old.parquet"
        save_event_snapshot(old_events, snap)
        result = compare_snapshots(snap, new_events)
        assert result.n_revised == 1
        assert result.total_revision_magnitude == 989  # 999 - 10


# ---- Storage ----


class TestSaveEventSnapshotGreen:

    def test_creates_parquet(self, tmp_path: Path) -> None:
        path = tmp_path / "snap.parquet"
        save_event_snapshot(_make_events(), path)
        assert path.exists()
        table = pq.read_table(path)
        assert table.num_rows == 3

    def test_preserves_all_fields(self, tmp_path: Path) -> None:
        events = _make_events(1)
        path = tmp_path / "snap.parquet"
        save_event_snapshot(events, path)
        table = pq.read_table(path)
        for field_name in events[0]:
            assert field_name in table.column_names

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        path = tmp_path / "deep" / "nested" / "snap.parquet"
        save_event_snapshot(_make_events(1), path)
        assert path.exists()


class TestSaveEventSnapshotBeige:

    def test_empty_events_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="No events"):
            save_event_snapshot([], tmp_path / "empty.parquet")


class TestSaveEventSnapshotRed:
    """C-233 (#326): atomic writes — a crash mid-write must never
    leave a truncated Parquet at the canonical path."""

    def test_crash_mid_write_leaves_no_target(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import datafactory_harvester.snapshot_storage as ss

        def _boom(*args: object, **kwargs: object) -> None:
            raise OSError("disk full mid-write")

        monkeypatch.setattr(ss.pq, "write_table", _boom)
        path = tmp_path / "snap.parquet"
        with pytest.raises(OSError, match="disk full"):
            save_event_snapshot(_make_events(), path)
        assert not path.exists()
        assert list(tmp_path.glob("*.tmp")) == []

    def test_crash_does_not_clobber_existing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A failed re-save must leave the previous snapshot intact."""
        import datafactory_harvester.snapshot_storage as ss

        path = tmp_path / "snap.parquet"
        save_event_snapshot(_make_events(), path)
        original = path.read_bytes()

        def _boom(*args: object, **kwargs: object) -> None:
            raise OSError("crash")

        monkeypatch.setattr(ss.pq, "write_table", _boom)
        with pytest.raises(OSError):
            save_event_snapshot(_make_events(), path)
        assert path.read_bytes() == original


class TestArchiveSnapshotGreen:

    def test_archives_existing_file(self, tmp_path: Path) -> None:
        from datafactory_harvester.snapshot_storage import archive_snapshot

        path = tmp_path / "snap.parquet"
        path.write_text("data")
        result = archive_snapshot(path)
        assert result is not None
        assert result.exists()
        assert not path.exists()

    def test_returns_none_for_missing_file(self, tmp_path: Path) -> None:
        from datafactory_harvester.snapshot_storage import archive_snapshot

        result = archive_snapshot(tmp_path / "nope.parquet")
        assert result is None

    def test_archive_lands_in_subdirectory(
        self, tmp_path: Path,
    ) -> None:
        """C-234 (#326): archives go to archive/ so consolidation
        globs structurally cannot see them."""
        from datafactory_harvester.snapshot_storage import archive_snapshot

        path = tmp_path / "acled_2020_2020.parquet"
        path.write_text("data")
        result = archive_snapshot(path)
        assert result is not None
        assert result.parent == tmp_path / "archive"
        # The source-dir glob used by consolidators no longer
        # matches the archived file.
        assert list(tmp_path.glob("*.parquet")) == []

    def test_save_archive_save_round_trip(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_harvester.snapshot_storage import archive_snapshot

        path = tmp_path / "snap.parquet"
        save_event_snapshot(_make_events(), path)
        archived = archive_snapshot(path)
        save_event_snapshot(_make_events(), path)
        assert path.exists()
        assert archived is not None and archived.exists()
        assert pq.read_table(path).num_rows == 3
        assert pq.read_table(archived).num_rows == 3


# ---- Source Registry ----


class TestSourceRegistryGreen:

    def test_register_and_fetch(self, tmp_path: Path) -> None:
        from datafactory_harvester.sources import (
            fetch_source,
            register_source,
        )

        def _fake_source(**kwargs: object) -> Path:
            return tmp_path / "result.parquet"

        register_source("test_source", _fake_source)
        result = fetch_source("test_source")
        assert result == tmp_path / "result.parquet"

    def test_unknown_source_raises(self) -> None:
        from datafactory_harvester.sources import fetch_source

        with pytest.raises(KeyError, match="Unknown source"):
            fetch_source("nonexistent_source_xyz")

    def test_list_sources(self) -> None:
        from datafactory_harvester.sources import list_sources

        sources = list_sources()
        assert isinstance(sources, list)
