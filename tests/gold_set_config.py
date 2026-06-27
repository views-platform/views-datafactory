"""Gold set paths and model configuration for parity tests."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GOLD_DIR = REPO_ROOT / "data" / "gold"
GOLD_PGM_AFRICA_ME = GOLD_DIR / "viewser_pgm_africa_me.parquet"

DATA_DIR = REPO_ROOT / "data" / "assembled"
GAUL_DIR = REPO_ROOT / "data" / "raw" / "gaul_admin"
VIEWPOINT_DIR = REPO_ROOT / "data" / "viewpoint"
COMPILED_DIR = REPO_ROOT / "data" / "compiled"
CONSOLIDATED_DIR = REPO_ROOT / "data" / "consolidated"

MONTH_ID_EPOCH = 1980
PARITY_THRESHOLD = 0.001  # 0.1%

FACTORY_FEATURES = ["ged_sb_best", "ged_ns_best", "ged_os_best"]
PARITY_FEATURES = FACTORY_FEATURES
