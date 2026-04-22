"""Falsification audit: shining_codex model executability.

Claim: "I can execute (load data, train and evaluate) the new model
shining_codex now."

F1 (resolved): ModelPathManager requires config_deployment.py and
config_sweep.py — both now exist.

F2 (resolved): Feature set matches novel_heuristics parity target
(lr_ged_sb_dep + lr_ged_sb, both from ged_sb_best country sum).
"""

from __future__ import annotations

from pathlib import Path

import pytest

_SHINING_CODEX = Path(__file__).resolve().parents[1].parent / (
    "views-models/models/shining_codex"
)

SKIP_REASON = "shining_codex not found at expected path"


@pytest.mark.skipif(
    not _SHINING_CODEX.exists(),
    reason=SKIP_REASON,
)
class TestF1ConfigFiles:
    """F1 (resolved): ModelPathManager requires config_deployment.py
    and config_sweep.py — both are checked at init with validate=True."""

    def test_config_deployment_exists(self) -> None:
        path = _SHINING_CODEX / "configs" / "config_deployment.py"
        assert path.exists()

    def test_config_sweep_exists(self) -> None:
        path = _SHINING_CODEX / "configs" / "config_sweep.py"
        assert path.exists()

    def test_all_required_configs_exist(self) -> None:
        required = [
            "config_deployment.py",
            "config_hyperparameters.py",
            "config_meta.py",
            "config_partitions.py",
            "config_queryset.py",
            "config_sweep.py",
        ]
        configs_dir = _SHINING_CODEX / "configs"
        for name in required:
            assert (configs_dir / name).exists(), f"Missing {name}"


@pytest.mark.skipif(
    not _SHINING_CODEX.exists(),
    reason=SKIP_REASON,
)
class TestF2FeatureParity:
    """F2 (resolved): shining_codex output matches novel_heuristics
    column contract — lr_ged_sb_dep (feature) + lr_ged_sb (target)."""

    def test_feature_rename_produces_target(self) -> None:
        source = (_SHINING_CODEX / "configs" / "config_queryset.py").read_text()
        assert '"ged_sb_best": "lr_ged_sb"' in source
        assert 'lr_ged_sb_dep' in source
