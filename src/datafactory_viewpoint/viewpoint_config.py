"""Viewpoint configuration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ViewpointConfig:
    """Configuration for building a viewpoint from a consolidated store.

    Declares which survivorship and distribution strategies to apply,
    the version tag, and I/O paths. Strategy names are looked up
    in the strategy registries at build time.

    consolidated_path existence is checked at build time, not config
    time (the file may not exist yet).
    """

    # Input
    consolidated_path: Path

    # Output
    output_path: Path = Path("data/viewpoints/ucdp_v1.parquet")
    ledger_path: Path = Path(
        "provenance/viewpoint/ucdp_v1_ledger.jsonl"
    )

    # Strategy selection
    survivorship_strategy: str = "annual_wins"
    distribution_strategy: str = "even_split"

    # Filtering (applied after survivorship + distribution)
    # None means no filter; profiles set values for production parity
    min_priogrid_gid: int | None = None
    max_type_of_violence: int | None = None
    exclude_where_prec: tuple[int, ...] = ()

    # Version tag for provenance (set by profile or caller)
    version: str = "custom"
