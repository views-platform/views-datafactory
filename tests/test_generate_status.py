"""Tests for generate_status.py — pipeline status page (issue #101).

TDD: these tests define the contract. The script generates a static
HTML page showing a source-by-stage matrix with colored status dots.
"""

from __future__ import annotations

import ast
import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from datafactory_provenance.source_registry import PIPELINE_SOURCES

SCRIPT = Path(__file__).parent.parent / "scripts" / "generate_status.py"

import sys as _sys  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "generate_status", SCRIPT,
)
_mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_sys.modules["generate_status"] = _mod
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]

ALL_STAGES = _mod.ALL_STAGES
SOURCE_STAGES = _mod.SOURCE_STAGES
StageArtifact = _mod.StageArtifact
check_stage = _mod.check_stage
generate_html = _mod.generate_html


class TestStageArtifact:
    """Frozen dataclass for stage artifact declarations."""

    def test_construction_with_defaults(self) -> None:
        sa = StageArtifact()
        assert sa.data_glob is None
        assert sa.artifact is None
        assert sa.ledger is None
        assert sa.features == ()

    def test_construction_with_values(self) -> None:
        sa = StageArtifact(
            data_glob="data/raw/test/*.parquet",
            ledger="test/ingestion_ledger.jsonl",
        )
        assert sa.data_glob == "data/raw/test/*.parquet"
        assert sa.ledger == "test/ingestion_ledger.jsonl"

    def test_frozen(self) -> None:
        sa = StageArtifact()
        with pytest.raises(AttributeError):
            sa.data_glob = "x"  # type: ignore[misc]


class TestSourceStages:
    """Structural invariants on the SOURCE_STAGES mapping."""

    def test_all_names_map_to_pipeline_sources(self) -> None:
        registry_names = {s.name for s in PIPELINE_SOURCES}
        for name in SOURCE_STAGES:
            match = (
                name in registry_names
                or any(r.startswith(name) for r in registry_names)
            )
            assert match, (
                f"{name!r} in SOURCE_STAGES has no corresponding "
                f"PIPELINE_SOURCES entry"
            )

    def test_event_sources_have_consolidation(self) -> None:
        for name in ("UCDP", "ACLED"):
            stages = SOURCE_STAGES[name]
            assert "consolidation" in stages, (
                f"{name} is an event source and must have "
                f"consolidation stage"
            )
            assert stages["consolidation"] is not None

    def test_raster_sources_skip_consolidation(self) -> None:
        for name in ("GHS-POP", "GHS-BUILT-S", "V-Dem"):
            stages = SOURCE_STAGES[name]
            assert stages.get("consolidation") is None, (
                f"{name} is a raster source and must not have "
                f"consolidation stage"
            )

    def test_static_sources_have_only_harvest_assembly_zarr(
        self,
    ) -> None:
        for name in ("PRIO-GRID Static", "GAUL Admin"):
            stages = SOURCE_STAGES[name]
            active = {
                k for k, v in stages.items() if v is not None
            }
            assert active == {"harvest", "assembly", "zarr"}, (
                f"{name} should have only harvest+assembly+zarr, "
                f"got {active}"
            )

    def test_shdi_harvest_only_integrated(self) -> None:
        stages = SOURCE_STAGES["SHDI"]
        integrated = {
            k for k, v in stages.items()
            if isinstance(v, StageArtifact)
        }
        assert integrated == {"harvest"}, (
            f"SHDI should have only harvest integrated, "
            f"got {integrated}"
        )

    def test_shdi_downstream_not_yet_integrated(self) -> None:
        stages = SOURCE_STAGES["SHDI"]
        for stage in ("viewpoint", "compilation", "assembly", "zarr"):
            assert stages[stage] == "not_yet_integrated", (
                f"SHDI {stage} should be 'not_yet_integrated'"
            )

    def test_every_active_stage_has_check_field(self) -> None:
        for name, stages in SOURCE_STAGES.items():
            for stage_name, sa in stages.items():
                if sa is None or isinstance(sa, str):
                    continue
                has_check = (
                    sa.data_glob is not None
                    or sa.artifact is not None
                    or sa.features != ()
                )
                assert has_check, (
                    f"{name}/{stage_name}: StageArtifact has no "
                    f"check field (data_glob, artifact, features)"
                )

    def test_all_stages_column_order(self) -> None:
        expected = (
            "harvest", "consolidation", "viewpoint",
            "compilation", "assembly", "zarr",
        )
        assert expected == ALL_STAGES


class TestCheckStage:
    """check_stage() evaluates a single source×stage cell."""

    def test_none_returns_not_applicable(self) -> None:
        result = check_stage(
            artifact=None,
            data_dir=Path("/tmp"),
            provenance_dir=Path("/tmp"),
            now=datetime.now(tz=UTC),
            slo_hours=744,
        )
        assert result["status"] == "not_applicable"

    def test_string_sentinel_passes_through(self) -> None:
        result = check_stage(
            artifact="not_yet_integrated",
            data_dir=Path("/tmp"),
            provenance_dir=Path("/tmp"),
            now=datetime.now(tz=UTC),
            slo_hours=744,
        )
        assert result["status"] == "not_yet_integrated"

    def test_artifact_exists_fresh_returns_green(
        self, tmp_path: Path,
    ) -> None:
        data = tmp_path / "data"
        data.mkdir()
        (data / "store.parquet").write_text("x")
        prov = tmp_path / "prov"
        prov.mkdir()
        ledger = prov / "ledger.jsonl"
        now = datetime.now(tz=UTC)
        entry = {"timestamp": now.isoformat(), "outcome": "success"}
        ledger.write_text(json.dumps(entry) + "\n")
        sa = StageArtifact(
            artifact="store.parquet",
            ledger="ledger.jsonl",
        )
        result = check_stage(
            artifact=sa,
            data_dir=data,
            provenance_dir=prov,
            now=now,
            slo_hours=744,
        )
        assert result["status"] == "ok"

    def test_artifact_exists_stale_returns_yellow(
        self, tmp_path: Path,
    ) -> None:
        data = tmp_path / "data"
        data.mkdir()
        (data / "store.parquet").write_text("x")
        prov = tmp_path / "prov"
        prov.mkdir()
        ledger = prov / "ledger.jsonl"
        now = datetime.now(tz=UTC)
        old = now.replace(year=now.year - 1)
        entry = {"timestamp": old.isoformat(), "outcome": "success"}
        ledger.write_text(json.dumps(entry) + "\n")
        sa = StageArtifact(
            artifact="store.parquet",
            ledger="ledger.jsonl",
        )
        result = check_stage(
            artifact=sa,
            data_dir=data,
            provenance_dir=prov,
            now=now,
            slo_hours=744,
        )
        assert result["status"] == "stale"

    def test_artifact_missing_returns_red(
        self, tmp_path: Path,
    ) -> None:
        sa = StageArtifact(
            artifact="store.parquet",
            ledger="ledger.jsonl",
        )
        result = check_stage(
            artifact=sa,
            data_dir=tmp_path,
            provenance_dir=tmp_path,
            now=datetime.now(tz=UTC),
            slo_hours=744,
        )
        assert result["status"] == "missing"

    def test_harvest_glob_present(
        self, tmp_path: Path,
    ) -> None:
        data = tmp_path / "data"
        raw = data / "raw" / "test"
        raw.mkdir(parents=True)
        (raw / "2024.parquet").write_text("x")
        prov = tmp_path / "prov"
        prov.mkdir()
        ledger = prov / "ledger.jsonl"
        now = datetime.now(tz=UTC)
        entry = {"timestamp": now.isoformat(), "outcome": "success"}
        ledger.write_text(json.dumps(entry) + "\n")
        sa = StageArtifact(
            data_glob="raw/test/*.parquet",
            ledger="ledger.jsonl",
        )
        result = check_stage(
            artifact=sa,
            data_dir=data,
            provenance_dir=prov,
            now=now,
            slo_hours=744,
        )
        assert result["status"] == "ok"

    def test_static_slo_none_always_fresh(
        self, tmp_path: Path,
    ) -> None:
        data = tmp_path / "data"
        data.mkdir()
        (data / "store.parquet").write_text("x")
        prov = tmp_path / "prov"
        prov.mkdir()
        ledger = prov / "ledger.jsonl"
        now = datetime.now(tz=UTC)
        old = now.replace(year=now.year - 5)
        entry = {"timestamp": old.isoformat(), "outcome": "success"}
        ledger.write_text(json.dumps(entry) + "\n")
        sa = StageArtifact(
            artifact="store.parquet",
            ledger="ledger.jsonl",
        )
        result = check_stage(
            artifact=sa,
            data_dir=data,
            provenance_dir=prov,
            now=now,
            slo_hours=None,
        )
        assert result["status"] == "ok"


class TestGenerateHtml:
    """generate_html() produces valid HTML with the status matrix."""

    def _make_results(self) -> dict:
        now = datetime.now(tz=UTC)
        results: dict = {}
        for name, stages in SOURCE_STAGES.items():
            results[name] = {}
            for stage_name, sa in stages.items():
                if sa is None:
                    results[name][stage_name] = {
                        "status": "not_applicable",
                    }
                else:
                    results[name][stage_name] = {
                        "status": "ok",
                        "timestamp": now.isoformat()[:19],
                    }
        return results

    def test_output_is_valid_html(self) -> None:
        html = generate_html(
            self._make_results(),
            datetime.now(tz=UTC),
        )
        assert "<!DOCTYPE html>" in html
        assert "</html>" in html

    def test_contains_all_source_names(self) -> None:
        html = generate_html(
            self._make_results(),
            datetime.now(tz=UTC),
            tag="v1.0.0",
        )
        for name in SOURCE_STAGES:
            assert name in html, f"source {name!r} not in HTML"

    def test_source_names_link_to_data_cards(self) -> None:
        html = generate_html(
            self._make_results(),
            datetime.now(tz=UTC),
            tag="v1.2.26",
        )
        assert "blob/v1.2.26/docs/sources/ucdp.md" in html
        assert "blob/v1.2.26/docs/sources/shdi.md" in html

    def test_contains_all_stage_headers(self) -> None:
        html = generate_html(
            self._make_results(),
            datetime.now(tz=UTC),
        )
        for stage in ALL_STAGES:
            assert stage.capitalize() in html or stage in html, (
                f"stage {stage!r} header not in HTML"
            )

    def test_contains_feature_count(self) -> None:
        html = generate_html(
            self._make_results(),
            datetime.now(tz=UTC),
        )
        assert "75" in html


class TestScriptStructure:
    """Script follows project conventions (check_health.py pattern)."""

    def test_has_main_function(self) -> None:
        tree = ast.parse(SCRIPT.read_text())
        func_names = [
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
        ]
        assert "main" in func_names

    def test_has_sys_exit_main(self) -> None:
        source = SCRIPT.read_text()
        assert "sys.exit(main())" in source
