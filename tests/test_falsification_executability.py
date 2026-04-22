"""Falsification audit: shining_codex + bright_starship executability.

Claim: "I can execute (load data, train and evaluate) the new models
shining_codex and bright_starship now."

F6 (resolved): shining_codex was missing required directories — now
created (artifacts, data, data/raw, logs, notebooks, reports).

F9 (resolved via metadata): forecasting partition extends beyond
observed UCDP data. Fixed by adding last_valid_month_id metadata to
zarr attrs and load_dataset() warning when requesting beyond it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_MODELS_ROOT = Path(__file__).resolve().parents[1].parent / "views-models/models"
_SHINING_CODEX = _MODELS_ROOT / "shining_codex"
_BRIGHT_STARSHIP = _MODELS_ROOT / "bright_starship"

SKIP_SC = "shining_codex not found at expected path"
SKIP_BS = "bright_starship not found at expected path"


@pytest.mark.skipif(not _SHINING_CODEX.exists(), reason=SKIP_SC)
class TestF6ShiningCodexDirectories:
    """F6 (resolved): ModelPathManager requires these directories at
    init time when validate=True (the default)."""

    REQUIRED_DIRS = [
        "artifacts",
        "data",
        "data/raw",
        "logs",
        "notebooks",
        "reports",
    ]

    @pytest.mark.parametrize("subdir", REQUIRED_DIRS)
    def test_required_directory_exists(self, subdir: str) -> None:
        path = _SHINING_CODEX / subdir
        assert path.is_dir(), (
            f"Missing {subdir}/ — ModelPathManager(validate=True) will raise"
        )


class TestF9DataBoundaryMetadata:
    """F9 (resolved): zarr store and npy provenance should expose
    last_valid_month_id so consumers know where observed data ends."""

    def test_provenance_has_last_valid_month_id(self) -> None:
        import json

        prov_path = (
            Path(__file__).resolve().parents[1]
            / "data" / "assembled" / "provenance.json"
        )
        if not prov_path.exists():
            pytest.skip("assembled provenance.json not found")
        prov = json.loads(prov_path.read_text())
        assert "last_valid_month_id" in prov, (
            "provenance.json missing last_valid_month_id — "
            "run scripts/assemble_grid.py to regenerate"
        )
        assert isinstance(prov["last_valid_month_id"], int)
        assert prov["last_valid_month_id"] > 0

    def test_load_dataset_warns_beyond_valid_data(self) -> None:
        """load_dataset should warn when end exceeds observed data."""
        import json

        prov_path = (
            Path(__file__).resolve().parents[1]
            / "data" / "assembled" / "provenance.json"
        )
        if not prov_path.exists():
            pytest.skip("assembled data not found")

        prov = json.loads(prov_path.read_text())
        last_valid = prov.get("last_valid_month_id")
        if last_valid is None:
            pytest.skip("last_valid_month_id not in provenance")

        from datafactory_query import load_dataset

        with pytest.warns(UserWarning, match="exceeds last observed"):
            load_dataset(
                region="africa_me_legacy",
                features=["ged_sb_best"],
                output_format="dataframe",
                start=last_valid,
                end=last_valid + 5,
            )
