"""Viewpoint configuration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from datafactory_viewpoint.survivorship import get_survivorship
from datafactory_viewpoint.temporal_distribution import (
    get_distribution,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ViewpointConfig:
    """Configuration for building a viewpoint from a consolidated store.

    Declares which survivorship and distribution strategies to apply,
    the version tag, and I/O paths. Strategy names are validated
    against the strategy registries at config time.

    consolidated_path existence is checked at build time, not config
    time (the file may not exist yet).
    """

    # Input
    consolidated_path: Path

    # Output
    output_path: Path = Path("data/viewpoint/ucdp_v1.parquet")
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

    def __post_init__(self) -> None:
        if not self.version:
            err_msg = "version must be non-empty"
            logger.error(err_msg)
            raise ValueError(err_msg)
        try:
            get_survivorship(self.survivorship_strategy)
        except KeyError as exc:
            err_msg = (
                f"Unknown survivorship strategy: "
                f"'{self.survivorship_strategy}'"
            )
            logger.error(err_msg)
            raise ValueError(err_msg) from exc
        try:
            get_distribution(self.distribution_strategy)
        except KeyError as exc:
            err_msg = (
                f"Unknown distribution strategy: "
                f"'{self.distribution_strategy}'"
            )
            logger.error(err_msg)
            raise ValueError(err_msg) from exc
