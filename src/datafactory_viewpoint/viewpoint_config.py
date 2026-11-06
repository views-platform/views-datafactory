"""Viewpoint configuration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from datafactory_viewpoint.spatial_distribution import (
    get_spatial_distribution,
)
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
    spatial_distribution_strategy: str = "proportional"

    #: Seed for any stochastic distribution strategy.
    #:
    #: Currently **unused**: every registered strategy is deterministic,
    #: and there is no randomness anywhere in this layer. It is declared
    #: now because ADR-014 Principle 3 requires the viewpoint builder to be
    #: "a pure function of (consolidated store + configuration)", and a
    #: sampler only satisfies that if its seed is part of the
    #: configuration. Stating the contract before the first stochastic
    #: strategy arrives is cheaper than retrofitting it afterwards, and the
    #: seed is written to the provenance ledger from day one so a
    #: reproducibility record exists for builds that do not yet need it.
    #:
    #: ``None`` means "no stochastic strategy is in use". A stochastic
    #: strategy must reject ``None`` rather than silently seeding itself
    #: from entropy, which would break ADR-014 Principle 3 invisibly.
    #:
    #: See ADR-049's *Amendment 2026-11-05* for why sampling is a viewpoint
    #: concern at all, and ``reports/2026-11-04_summary_event_allocation_dossier``
    #: for the method this anticipates.
    seed: int | None = None

    # GAUL crosswalk paths for spatial distribution
    gaul1_crosswalk_path: Path = Path(
        "data/raw/gaul_admin/gaul1_code.parquet"
    )
    gaul0_crosswalk_path: Path = Path(
        "data/raw/gaul_admin/gaul0_code.parquet"
    )

    # Pre-processing
    filter_stale_versions: bool = True

    # Per-source-type distribution overrides.
    # Keys: source type strings ("annual", "dot9", "candidate").
    # Values: registered distribution strategy names.
    # When None, distribution_strategy applies uniformly.
    source_distribution_map: dict[str, str] | None = None

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
        try:
            get_spatial_distribution(
                self.spatial_distribution_strategy,
            )
        except KeyError as exc:
            err_msg = (
                f"Unknown spatial distribution strategy: "
                f"'{self.spatial_distribution_strategy}'"
            )
            logger.error(err_msg)
            raise ValueError(err_msg) from exc
        if self.source_distribution_map is not None:
            for src, strat in self.source_distribution_map.items():
                try:
                    get_distribution(strat)
                except KeyError as exc:
                    err_msg = (
                        f"Unknown distribution strategy "
                        f"'{strat}' for source type "
                        f"'{src}' in source_distribution_map"
                    )
                    logger.error(err_msg)
                    raise ValueError(err_msg) from exc

    @classmethod
    def from_shortcuts(
        cls, *, consolidated_path: Path,
    ) -> ViewpointConfig:
        """Construct config from minimal shortcut arguments."""
        return cls(consolidated_path=consolidated_path)
