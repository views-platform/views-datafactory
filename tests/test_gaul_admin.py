"""Tests for datafactory_harvester.sources.gaul_admin."""

from __future__ import annotations

import io
import json
import logging
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import shapefile as shp

from datafactory_harvester.sources.gaul_admin import (
    ADMIN_VARIABLES,
    GaulAdminConfig,
    _spatial_join,
)


def _make_fake_shp_zip() -> bytes:
    """Create a minimal in-memory ZIP with a fake .shp file."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("test.shp", "fake shapefile")
        zf.writestr("test.dbf", "fake dbf")
    return buf.getvalue()


class TestDownloadShapefileZip:

    def test_retries_on_transient_failure(self, tmp_path: Path) -> None:
        """_download_shapefile_zip uses request_with_retry (C-82)."""
        from datafactory_harvester.sources.gaul_admin import (
            _download_shapefile_zip,
        )

        fake_zip = _make_fake_shp_zip()
        mock_resp = MagicMock()
        mock_resp.content = fake_zip

        import requests as _req

        with (
            patch("datafactory_http.retry.requests.request") as mock_request,
            patch("datafactory_http.retry.time.sleep"),
        ):
            mock_request.side_effect = [
                _req.ConnectionError("transient"),
                mock_resp,
            ]
            result = _download_shapefile_zip(
                "http://example.com/test.zip",
                tmp_path / "cache",
                timeout=10,
            )

        assert mock_request.call_count == 2
        assert result.suffix == ".shp"
        assert result.exists()

    def test_skips_download_when_cached(self, tmp_path: Path) -> None:
        """When .shp already exists, skip download."""
        from datafactory_harvester.sources.gaul_admin import (
            _download_shapefile_zip,
        )

        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        (cache_dir / "test.shp").write_text("cached")

        with patch("datafactory_http.retry.requests.request") as mock_request:
            result = _download_shapefile_zip(
                "http://example.com/test.zip",
                cache_dir,
            )

        mock_request.assert_not_called()
        assert result.name == "test.shp"


# ---- GaulAdminConfig Green ----


class TestGaulAdminConfigGreen:

    def test_defaults(self) -> None:
        cfg = GaulAdminConfig()
        assert cfg.timeout == 300
        assert cfg.variables is None
        assert "gaul_admin" in str(cfg.data_dir)

    def test_frozen(self) -> None:
        cfg = GaulAdminConfig()
        with pytest.raises(AttributeError):
            cfg.timeout = 1  # type: ignore[misc]

    def test_custom_variables(self) -> None:
        cfg = GaulAdminConfig(variables=("gaul0_code",))
        assert cfg.variables == ("gaul0_code",)


# ---- GaulAdminConfig Beige ----


class TestGaulAdminConfigBeige:

    def test_rejects_zero_timeout(self) -> None:
        with pytest.raises(ValueError, match="timeout"):
            GaulAdminConfig(timeout=0)

    def test_rejects_negative_timeout(self) -> None:
        with pytest.raises(ValueError, match="timeout"):
            GaulAdminConfig(timeout=-5)


# ---- GaulAdminConfig Red ----


class TestGaulAdminConfigRed:

    def test_mutation_rejected(self) -> None:
        cfg = GaulAdminConfig()
        with pytest.raises(AttributeError):
            cfg.variables = ("gaul0_code",)  # type: ignore[misc]


# ---- ADR-008 compliance ----


class TestGaulAdminADR008:

    def test_timeout_error_raised(self) -> None:
        with pytest.raises(ValueError, match="timeout"):
            GaulAdminConfig(timeout=0)


# ---- C-188: failure path writes ledger entry ----

_GAUL_MODULE = "datafactory_harvester.sources.gaul_admin"


class TestGaulAdminFailureLedger:

    def test_write_variable_failure_records_ledger_entry(
        self, tmp_path: Path,
    ) -> None:
        """When _write_variable raises, a 'failed' entry must
        appear in the provenance ledger (C-188)."""
        ledger = tmp_path / "ledger.jsonl"
        config = GaulAdminConfig(
            data_dir=tmp_path / "data",
            cache_dir=tmp_path / "cache",
            ledger_path=ledger,
            variables=("gaul0_code",),
        )

        with (
            patch(f"{_GAUL_MODULE}._download_shapefile_zip") as mock_dl,
            patch(f"{_GAUL_MODULE}._load_centroids") as mock_cen,
            patch(f"{_GAUL_MODULE}._spatial_join") as mock_sj,
            patch(f"{_GAUL_MODULE}._write_variable") as mock_wv,
        ):
            mock_dl.return_value = tmp_path / "fake.shp"
            mock_cen.return_value = []
            mock_sj.return_value = {}
            mock_wv.side_effect = RuntimeError("disk full")

            from datafactory_harvester.sources.gaul_admin import (
                fetch_gaul_admin,
            )

            results = fetch_gaul_admin(config, force_refresh=True)

        assert results[0]["outcome"] == "failed"

        entries = [
            json.loads(line)
            for line in ledger.read_text().splitlines()
            if line.strip()
        ]
        failed = [e for e in entries if e.get("outcome") == "failed"]
        assert len(failed) == 1, (
            f"Expected 1 failed ledger entry, got {len(failed)}"
        )
        assert failed[0]["version"] == "gaul0_code"
        assert failed[0]["dataset"] == "gaul_admin"
        assert "disk full" in failed[0]["errors"][0]


# ---- Spatial join tests (C-268, #211) ----


def _write_polygon_shapefile(
    path: Path,
    polygons: list[list[tuple[float, float]]],
    field_values: list[dict[str, object]],
    field_specs: list[tuple[str, str]],
) -> Path:
    """Write synthetic polygons to a shapefile for testing."""
    path.parent.mkdir(parents=True, exist_ok=True)
    stem = str(path.with_suffix(""))
    w = shp.Writer(stem)
    for name, ftype in field_specs:
        if ftype == "N":
            w.field(name, "N", decimal=0)
        else:
            w.field(name, "C", size=50)
    for poly, vals in zip(polygons, field_values, strict=True):
        w.poly([poly])
        w.record(**vals)
    w.close()
    return path


class TestSpatialJoinCharacterization:
    """C-268: spatial join coverage for _spatial_join()."""

    def test_centroid_inside_polygon_matched(
        self, tmp_path: Path,
    ) -> None:
        """Centroid inside a polygon gets the polygon's attributes."""
        shp_path = tmp_path / "admin.shp"
        _write_polygon_shapefile(
            shp_path,
            polygons=[
                [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)],
            ],
            field_values=[{"ADM0_CODE": 42, "ADM0_NAME": "Test"}],
            field_specs=[("ADM0_CODE", "N"), ("ADM0_NAME", "C")],
        )

        centroids = [(1, 5.0, 5.0)]  # (gid, lon, lat) — inside
        result = _spatial_join(
            centroids, shp_path, ["ADM0_CODE", "ADM0_NAME"],
        )

        assert 1 in result
        assert result[1]["ADM0_CODE"] == 42
        assert result[1]["ADM0_NAME"] == "Test"

    def test_centroid_outside_polygon_unmatched(
        self, tmp_path: Path,
    ) -> None:
        """Centroid outside all polygons is not in the result."""
        shp_path = tmp_path / "admin.shp"
        _write_polygon_shapefile(
            shp_path,
            polygons=[
                [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)],
            ],
            field_values=[{"ADM0_CODE": 42, "ADM0_NAME": "Test"}],
            field_specs=[("ADM0_CODE", "N"), ("ADM0_NAME", "C")],
        )

        centroids = [(99, 50.0, 50.0)]  # outside
        result = _spatial_join(
            centroids, shp_path, ["ADM0_CODE", "ADM0_NAME"],
        )

        assert 99 not in result

    def test_multiple_polygons_correct_assignment(
        self, tmp_path: Path,
    ) -> None:
        """Two non-overlapping polygons: each centroid maps correctly."""
        shp_path = tmp_path / "admin.shp"
        _write_polygon_shapefile(
            shp_path,
            polygons=[
                [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)],
                [(20, 20), (30, 20), (30, 30), (20, 30), (20, 20)],
            ],
            field_values=[
                {"ADM0_CODE": 1, "ADM0_NAME": "Alpha"},
                {"ADM0_CODE": 2, "ADM0_NAME": "Beta"},
            ],
            field_specs=[("ADM0_CODE", "N"), ("ADM0_NAME", "C")],
        )

        centroids = [
            (10, 5.0, 5.0),    # inside Alpha
            (20, 25.0, 25.0),  # inside Beta
            (30, 50.0, 50.0),  # outside both
        ]
        result = _spatial_join(
            centroids, shp_path, ["ADM0_CODE", "ADM0_NAME"],
        )

        assert result[10]["ADM0_NAME"] == "Alpha"
        assert result[20]["ADM0_NAME"] == "Beta"
        assert 30 not in result

    def test_admin_variables_complete(self) -> None:
        """ADMIN_VARIABLES has all 7 expected keys."""
        expected = {
            "gaul0_code", "gaul1_code", "gaul2_code",
            "gaul0_name", "gaul1_name", "gaul2_name",
            "iso3_code",
        }
        assert set(ADMIN_VARIABLES.keys()) == expected


# ---- Pipeline ordering guard (C-247, #211) ----


class TestGaulPipelineOrdering:
    """C-247: area-majority must run after centroid harvest."""

    def test_pipeline_runs_area_majority_after_centroid(
        self,
    ) -> None:
        """In refresh_pipeline.sh, generate_area_majority_gaul.py
        appears after harvest_gaul.py."""
        script = Path("scripts/refresh_pipeline.sh")
        lines = script.read_text().splitlines()

        centroid_line = None
        area_majority_line = None
        for i, line in enumerate(lines):
            if "harvest_gaul.py" in line:
                centroid_line = i
            if "generate_area_majority_gaul.py" in line:
                area_majority_line = i

        assert centroid_line is not None, (
            "harvest_gaul.py not found in refresh_pipeline.sh"
        )
        assert area_majority_line is not None, (
            "generate_area_majority_gaul.py not found"
        )
        assert area_majority_line > centroid_line, (
            f"area-majority (L{area_majority_line}) must run "
            f"after centroid harvest (L{centroid_line})"
        )


# ---- Fuvahmulah-signature cell verification (C-292, #211) ----


class TestFuvahmulahVerification:
    """C-292: Fuvahmulah-signature cells must be classified."""

    _CLASSIFICATION_PATH = Path(
        "reports/investigation_gaul_excluded_cells/"
        "excluded_cell_classification.json"
    )
    _FUVAHMULAH_PGIDS = {118753, 129574, 132525}

    def test_fuvahmulah_cells_classified(self) -> None:
        """All 3 Fuvahmulah-signature pgids exist in classification."""
        data = json.loads(self._CLASSIFICATION_PATH.read_text())
        classified_gids = {e["gid"] for e in data}

        for pgid in self._FUVAHMULAH_PGIDS:
            assert pgid in classified_gids, (
                f"pgid {pgid} not in excluded cell classification"
            )

    def test_fuvahmulah_cells_have_resolution(self) -> None:
        """All 3 cells have a non-empty resolution field."""
        data = json.loads(self._CLASSIFICATION_PATH.read_text())
        fuva = {
            e["gid"]: e for e in data
            if e["gid"] in self._FUVAHMULAH_PGIDS
        }

        for pgid in self._FUVAHMULAH_PGIDS:
            entry = fuva[pgid]
            assert entry.get("resolution"), (
                f"pgid {pgid} has no resolution"
            )
            assert entry["classification"] == "coastal_resolution_gap"


# ---- Nesting check wired (C-250, #211) ----


def _load_area_majority_module():  # type: ignore[no-untyped-def]
    """Load generate_area_majority_gaul.py from scripts/."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "gen_gaul", "scripts/generate_area_majority_gaul.py",
    )
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


class TestNestingCheckWired:
    """C-250: reconciliation nesting check wired into area-majority."""

    def test_nesting_check_importable(self) -> None:
        """generate_area_majority_gaul imports check_nesting."""
        mod = _load_area_majority_module()
        assert hasattr(mod, "check_nesting")

    def test_check_nesting_integrity_clean(self) -> None:
        """_check_nesting_integrity logs no warnings on clean data."""
        mod = _load_area_majority_module()
        code_assignments = {
            "gaul0_code": {1: 10, 2: 10, 3: 20},
            "gaul1_code": {1: 100, 2: 101, 3: 200},
            "gaul2_code": {1: 1000, 2: 1001, 3: 2000},
        }
        mod._check_nesting_integrity(code_assignments)

    def test_check_nesting_integrity_violation_logged(
        self, caplog: pytest.LogCaptureFixture,
    ) -> None:
        """_check_nesting_integrity logs violations as warnings."""
        mod = _load_area_majority_module()
        # L1=100 maps to both L0=10 and L0=20 — a nesting violation
        code_assignments = {
            "gaul0_code": {1: 10, 2: 20},
            "gaul1_code": {1: 100, 2: 100},
            "gaul2_code": {1: 1000, 2: 2000},
        }
        with caplog.at_level(logging.WARNING):
            mod._check_nesting_integrity(code_assignments)

        assert any(
            "nesting violation" in r.message.lower()
            for r in caplog.records
        )
