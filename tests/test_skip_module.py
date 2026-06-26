"""Unit tests for datafactory_provenance.skip — the content-addressed skip module.

Tests SkipVerdict, check_assembly_skip, and check_export_skip in isolation
using tmp_path fixtures. No subprocess invocation, no synthetic pipeline.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from datafactory_provenance import compute_file_digest
from datafactory_provenance.skip import (
    check_assembly_skip,
    check_export_skip,
)


def _write_output(path: Path, content: bytes = b"grid-content") -> str:
    """Write a file and return its digest."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return compute_file_digest(path)


def _write_provenance(
    path: Path,
    sources: dict[str, str | None],
    output_digest: str,
) -> None:
    """Write a minimal provenance.json."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "sources": sources,
        "output_digest": output_digest,
    }))


# ── Assembly skip tests ──────────────────────────────────────


class TestCheckAssemblySkip:
    """Tests for check_assembly_skip."""

    def test_skip_when_all_digests_match(self, tmp_path: Path) -> None:
        output_path = tmp_path / "grid.npy"
        output_digest = _write_output(output_path)

        sources = {"ucdp_digest": "abc123", "acled_digest": "def456"}
        prov_path = tmp_path / "provenance.json"
        _write_provenance(prov_path, sources, output_digest)

        current = {"ucdp_digest": "abc123", "acled_digest": "def456"}
        verdict = check_assembly_skip(current, prov_path, output_path)

        assert verdict.should_skip is True
        assert verdict.changed_keys == ()
        assert verdict.missing_keys == ()
        assert verdict.output_valid is True

    def test_no_skip_when_provenance_missing(self, tmp_path: Path) -> None:
        output_path = tmp_path / "grid.npy"
        _write_output(output_path)
        prov_path = tmp_path / "provenance.json"

        current = {"ucdp_digest": "abc123"}
        verdict = check_assembly_skip(current, prov_path, output_path)

        assert verdict.should_skip is False
        assert "no previous" in verdict.reason.lower()

    def test_no_skip_when_output_missing(self, tmp_path: Path) -> None:
        output_path = tmp_path / "grid.npy"
        sources = {"ucdp_digest": "abc123"}
        prov_path = tmp_path / "provenance.json"
        _write_provenance(prov_path, sources, "some_digest")

        current = {"ucdp_digest": "abc123"}
        verdict = check_assembly_skip(current, prov_path, output_path)

        assert verdict.should_skip is False
        assert "no previous" in verdict.reason.lower()

    def test_no_skip_when_input_changed(self, tmp_path: Path) -> None:
        output_path = tmp_path / "grid.npy"
        output_digest = _write_output(output_path)

        sources = {"ucdp_digest": "abc123", "acled_digest": "def456"}
        prov_path = tmp_path / "provenance.json"
        _write_provenance(prov_path, sources, output_digest)

        current = {"ucdp_digest": "abc123", "acled_digest": "CHANGED"}
        verdict = check_assembly_skip(current, prov_path, output_path)

        assert verdict.should_skip is False
        assert "acled_digest" in verdict.changed_keys

    def test_no_skip_when_source_removed(self, tmp_path: Path) -> None:
        """C-260: prev has acled_digest but current doesn't — source was removed."""
        output_path = tmp_path / "grid.npy"
        output_digest = _write_output(output_path)

        sources = {"ucdp_digest": "abc123", "acled_digest": "def456"}
        prov_path = tmp_path / "provenance.json"
        _write_provenance(prov_path, sources, output_digest)

        current = {"ucdp_digest": "abc123"}
        verdict = check_assembly_skip(current, prov_path, output_path)

        assert verdict.should_skip is False
        assert "acled_digest" in verdict.missing_keys

    def test_no_skip_when_source_added(self, tmp_path: Path) -> None:
        """C-260: current has vdem_digest but prev doesn't — new source added."""
        output_path = tmp_path / "grid.npy"
        output_digest = _write_output(output_path)

        sources = {"ucdp_digest": "abc123"}
        prov_path = tmp_path / "provenance.json"
        _write_provenance(prov_path, sources, output_digest)

        current = {"ucdp_digest": "abc123", "vdem_digest": "new789"}
        verdict = check_assembly_skip(current, prov_path, output_path)

        assert verdict.should_skip is False
        assert "vdem_digest" in verdict.changed_keys

    def test_skip_ignores_none_valued_prev_digests(self, tmp_path: Path) -> None:
        """Absent sources recorded as None in provenance should not block skip."""
        output_path = tmp_path / "grid.npy"
        output_digest = _write_output(output_path)

        sources = {
            "ucdp_digest": "abc123",
            "acled_digest": "def456",
            "ghspop_digest": None,
            "vdem_digest": None,
        }
        prov_path = tmp_path / "provenance.json"
        _write_provenance(prov_path, sources, output_digest)

        current = {"ucdp_digest": "abc123", "acled_digest": "def456"}
        verdict = check_assembly_skip(current, prov_path, output_path)

        assert verdict.should_skip is True

    def test_no_skip_when_output_corrupt(self, tmp_path: Path) -> None:
        """C-262: inputs match but output file content doesn't match recorded digest."""
        output_path = tmp_path / "grid.npy"
        output_path.write_bytes(b"original-content")
        original_digest = compute_file_digest(output_path)

        sources = {"ucdp_digest": "abc123"}
        prov_path = tmp_path / "provenance.json"
        _write_provenance(prov_path, sources, original_digest)

        # Corrupt the output after provenance was written
        output_path.write_bytes(b"truncated")

        current = {"ucdp_digest": "abc123"}
        verdict = check_assembly_skip(current, prov_path, output_path)

        assert verdict.should_skip is False
        assert verdict.output_valid is False


# ── Export skip tests ─────────────────────────────────────────


class TestCheckExportSkip:
    """Tests for check_export_skip."""

    def test_export_skip_when_digests_match(self, tmp_path: Path) -> None:
        prov_path = tmp_path / "provenance.json"
        _write_provenance(prov_path, {}, "grid_digest_abc")

        zarr_dir = tmp_path / "grid.zarr"
        zarr_dir.mkdir()
        (zarr_dir / ".zattrs").write_text(json.dumps({
            "source_digest": "grid_digest_abc",
        }))

        verdict = check_export_skip(prov_path, zarr_dir)

        assert verdict.should_skip is True

    def test_export_no_skip_when_digests_differ(self, tmp_path: Path) -> None:
        prov_path = tmp_path / "provenance.json"
        _write_provenance(prov_path, {}, "grid_digest_abc")

        zarr_dir = tmp_path / "grid.zarr"
        zarr_dir.mkdir()
        (zarr_dir / ".zattrs").write_text(json.dumps({
            "source_digest": "stale_digest_xyz",
        }))

        verdict = check_export_skip(prov_path, zarr_dir)

        assert verdict.should_skip is False

    def test_export_no_skip_when_zarr_missing(self, tmp_path: Path) -> None:
        prov_path = tmp_path / "provenance.json"
        _write_provenance(prov_path, {}, "grid_digest_abc")

        zarr_dir = tmp_path / "grid.zarr"

        verdict = check_export_skip(prov_path, zarr_dir)

        assert verdict.should_skip is False


# ── Corrupted input tests (#282, C-280) ─────────────────────


class TestAssemblySkipCorruptedBeige:
    """Boundary: missing keys and null values in provenance."""

    def test_empty_provenance_file(self, tmp_path: Path) -> None:
        output_path = tmp_path / "grid.npy"
        _write_output(output_path)
        prov_path = tmp_path / "provenance.json"
        prov_path.write_text("")

        with pytest.raises(json.JSONDecodeError):
            check_assembly_skip({"ucdp_digest": "abc"}, prov_path, output_path)

    def test_missing_source_digest_key(self, tmp_path: Path) -> None:
        output_path = tmp_path / "grid.npy"
        output_digest = _write_output(output_path)
        prov_path = tmp_path / "provenance.json"
        prov_path.write_text(json.dumps({
            "output_digest": output_digest,
        }))

        current = {"ucdp_digest": "abc123"}
        verdict = check_assembly_skip(current, prov_path, output_path)
        assert verdict.should_skip is False

    def test_null_digest_values(self, tmp_path: Path) -> None:
        output_path = tmp_path / "grid.npy"
        output_digest = _write_output(output_path)
        prov_path = tmp_path / "provenance.json"
        prov_path.write_text(json.dumps({
            "sources": {"ucdp_digest": None, "acled_digest": None},
            "output_digest": output_digest,
        }))

        verdict = check_assembly_skip({}, prov_path, output_path)
        assert verdict.should_skip is True


class TestAssemblySkipCorruptedRed:
    """Adversarial: malformed JSON provenance crashes pipeline."""

    def test_malformed_json(self, tmp_path: Path) -> None:
        output_path = tmp_path / "grid.npy"
        _write_output(output_path)
        prov_path = tmp_path / "provenance.json"
        prov_path.write_text("{truncated")

        with pytest.raises(json.JSONDecodeError):
            check_assembly_skip({"ucdp_digest": "abc"}, prov_path, output_path)


class TestExportSkipCorruptedBeige:
    """Boundary: missing keys in export provenance."""

    def test_empty_provenance_file(self, tmp_path: Path) -> None:
        prov_path = tmp_path / "provenance.json"
        prov_path.write_text("")
        zarr_dir = tmp_path / "grid.zarr"
        zarr_dir.mkdir()
        (zarr_dir / ".zattrs").write_text(json.dumps({
            "source_digest": "abc",
        }))

        with pytest.raises(json.JSONDecodeError):
            check_export_skip(prov_path, zarr_dir)

    def test_missing_output_digest_key(self, tmp_path: Path) -> None:
        prov_path = tmp_path / "provenance.json"
        prov_path.write_text(json.dumps({"sources": {}}))
        zarr_dir = tmp_path / "grid.zarr"
        zarr_dir.mkdir()
        (zarr_dir / ".zattrs").write_text(json.dumps({
            "source_digest": "abc",
        }))

        verdict = check_export_skip(prov_path, zarr_dir)
        assert verdict.should_skip is False
        assert "not recorded" in verdict.reason


class TestExportSkipCorruptedRed:
    """Adversarial: malformed JSON in provenance and .zattrs."""

    def test_malformed_provenance_json(self, tmp_path: Path) -> None:
        prov_path = tmp_path / "provenance.json"
        prov_path.write_text("not json at all")
        zarr_dir = tmp_path / "grid.zarr"
        zarr_dir.mkdir()
        (zarr_dir / ".zattrs").write_text(json.dumps({
            "source_digest": "abc",
        }))

        with pytest.raises(json.JSONDecodeError):
            check_export_skip(prov_path, zarr_dir)

    def test_malformed_zattrs(self, tmp_path: Path) -> None:
        prov_path = tmp_path / "provenance.json"
        _write_provenance(prov_path, {}, "grid_digest_abc")
        zarr_dir = tmp_path / "grid.zarr"
        zarr_dir.mkdir()
        (zarr_dir / ".zattrs").write_text("{broken")

        with pytest.raises(json.JSONDecodeError):
            check_export_skip(prov_path, zarr_dir)
