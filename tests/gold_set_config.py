"""Gold set paths and model configuration for parity tests."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GOLD_DIR = REPO_ROOT / "data" / "gold"
GOLD_PGM_AFRICA_ME = GOLD_DIR / "viewser_pgm_africa_me.parquet"

DATA_DIR = REPO_ROOT / "data" / "assembled"
GAUL_DIR = REPO_ROOT / "data" / "raw" / "gaul_admin"
ZARR_PATH = DATA_DIR / "grid.zarr"
VIEWPOINT_DIR = REPO_ROOT / "data" / "viewpoint"
COMPILED_DIR = REPO_ROOT / "data" / "compiled"
CONSOLIDATED_DIR = REPO_ROOT / "data" / "consolidated"

MONTH_ID_EPOCH = 1980
PARITY_THRESHOLD = 0.001  # 0.1%

FEATURE_RENAME = {
    "ged_sb_best": "lr_sb_best",
    "ged_ns_best": "lr_ns_best",
    "ged_os_best": "lr_os_best",
}
FACTORY_FEATURES = list(FEATURE_RENAME.keys())
PARITY_FEATURES = list(FEATURE_RENAME.values())

MODEL_CONFIGS = {
    "pgm_africa_me": {
        "region": "africa_me_legacy",
        "output_format": "dataframe",
        "features": FACTORY_FEATURES,
        "expected_cells": 13110,
        "models": ["light_strider", "bright_starship"],
    },
    "pgm_land": {
        "region": "land",
        "output_format": "dataframe",
        "features": FACTORY_FEATURES,
        "expected_cells": 64818,
        "models": ["heavy_freighter", "heavy_strider"],
    },
    "cm_global": {
        "region": "global",
        "output_format": "country_month",
        "features": FACTORY_FEATURES,
        "models": ["shining_codex"],
    },
}
