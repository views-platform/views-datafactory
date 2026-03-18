"""Compilation configuration."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from datafactory_priogrid.grid_config import DEFAULT_GRID_CONFIG, GridConfig
from datafactory_priogrid.temporal_config import TemporalConfig
from datafactory_priogrid.temporal_generator import DEFAULT_TEMPORAL_CONFIG

logger = logging.getLogger(__name__)

# A feature spec is (feature_name, strategy_name)
FeatureSpec = tuple[str, str]


@dataclass(frozen=True)
class CompilationConfig:
    """Configuration for compiling source events onto the spatiotemporal grid.

    Features are declared as (name, strategy) pairs. The compiler
    never infers features from Parquet columns (ADR-003).
    """

    # Source
    source_path: Path

    # Grid
    grid_config: GridConfig = field(default_factory=lambda: DEFAULT_GRID_CONFIG)
    temporal_config: TemporalConfig = field(
        default_factory=lambda: DEFAULT_TEMPORAL_CONFIG
    )

    # Features to compute
    features: tuple[FeatureSpec, ...] = (
        ("event_count", "count"),
        ("fatalities", "sum_best"),
    )

    # Output
    output_dir: Path = Path("data/compiled")
    ledger_path: Path = Path("provenance/compiler/compilation_ledger.jsonl")

    # Column mapping (source Parquet field names)
    lat_field: str = "latitude"
    lon_field: str = "longitude"
    date_field: str = "date_start"

    def __post_init__(self) -> None:
        if not self.features:
            err_msg = "features must be non-empty"
            logger.error(err_msg)
            raise ValueError(err_msg)
        # source_path is validated at compile time (FileNotFoundError),
        # not at config construction time — the file may not exist yet.
