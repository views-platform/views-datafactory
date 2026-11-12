"""Compilation configuration."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar

from datafactory_priogrid.grid_config import DEFAULT_GRID_CONFIG, GridConfig
from datafactory_priogrid.temporal_config import TemporalConfig
from datafactory_priogrid.temporal_generator import DEFAULT_TEMPORAL_CONFIG

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FeatureSpec:
    """A single compiled feature: name, strategy, and optional filter.

    The filter dict maps event field names to required values.
    Only events matching ALL filter conditions are aggregated.
    Example: ``FeatureSpec("ged_sb_count", "count", {"type_of_violence": 1})``
    counts only state-based conflict events (UCDP type 1).
    """

    name: str
    strategy: str
    filter: dict[str, Any] = field(default_factory=dict)
    value_field: str = "best"


@dataclass(frozen=True)
class CompilationConfig:
    """Configuration for compiling source events onto the spatiotemporal grid.

    Features are declared as FeatureSpec instances. Each feature
    specifies a name, aggregation strategy, and optional filter
    for per-field disaggregation. The compiler never infers
    features from Parquet columns (ADR-003).
    """

    # Source
    source_path: Path

    # Grid
    grid_config: GridConfig = field(
        default_factory=lambda: DEFAULT_GRID_CONFIG
    )
    temporal_config: TemporalConfig = field(
        default_factory=lambda: DEFAULT_TEMPORAL_CONFIG
    )

    # Features to compute
    features: tuple[FeatureSpec, ...] = (
        FeatureSpec("event_count", "count"),
        FeatureSpec("fatalities", "sum_field"),
    )

    # Output
    output_dir: Path = Path("data/compiled")
    ledger_path: Path = Path("provenance/compiler/compilation_ledger.jsonl")

    # Column mapping (source Parquet field names)
    lat_field: str = "latitude"
    lon_field: str = "longitude"
    #: Column holding the month each row belongs to.
    #:
    #: The default is a RAW field, and that is a hazard rather than a
    #: convenience. The temporal allocator writes its decision to
    #: ``date_month`` and leaves ``date_start``/``date_end`` untouched,
    #: so a caller who takes this default on an allocated source
    #: collapses every distributed month back onto the event's start
    #: month -- the temporal twin of the spatial defect that cost 26.49%
    #: of UCDP fatality mass its placement. ``scripts/compile_grid.py``
    #: refuses to run in that configuration; see ``_reject_ignored_allocation``
    #: there.
    #:
    #: **This should be a required keyword argument, and is not, for one
    #: reason:** ``CompilationConfig`` is exported in
    #: ``datafactory_compilation.__all__`` and ships in the wheel, so
    #: removing the default is a breaking change for any external caller
    #: and belongs in a MAJOR release rather than a patch. Registered as
    #: such. An auto-detecting default -- ``None`` meaning "use
    #: ``date_month`` if the source has one" -- was considered and
    #: rejected: inferring decision-relevant semantics is what ADR-003
    #: forbids, and this defect is not worth fixing with a second
    #: instance of its own cause.
    date_field: str = "date_start"

    #: Column holding a cell the UPSTREAM STAGE HAS ALREADY DECIDED.
    #:
    #: When set, a row's value in this column wins over
    #: ``lat_field``/``lon_field``; the coordinates are the fallback for
    #: rows where it is null or out of range. That ordering is
    #: ADR-015's, stated in its section "priogrid_gid vs. Computed
    #: Cell": *"These can disagree (border cells, precision issues) …
    #: Viewpoint v1 should prefer priogrid_gid to match production."*
    #:
    #: It was declared there in June 2026 and never implemented. The
    #: spatial allocator records its decision by rewriting
    #: ``priogrid_gid`` and leaves the coordinates at the source
    #: centroid, so re-deriving the cell from the coordinates discarded
    #: every allocation: 1,128,236 deaths — 26.49% of UCDP fatality
    #: mass — were delivered to a cell other than the one chosen for
    #: them, with totals conserved, so no conservation check could see
    #: it. ``where_prec=6`` events collapsed from 6,896 chosen cells
    #: into 91 delivered ones.
    #:
    #: ``None`` by default, which is the pre-existing behaviour, because
    #: a decided cell is not something every source has. ACLED events
    #: are single-day points that no stage relocates
    #: (``acled_v1`` reports ``n_spatially_distributed=0``), so for
    #: ACLED the coordinates *are* the authority and this stays unset.
    #: ``PregriddedCompilationConfig.pgid_field`` is the same idea for
    #: sources that are gridded before they arrive; this is its
    #: event-shaped twin, and the asymmetry between the two is what let
    #: the defect exist.
    pgid_field: str | None = None

    # Output array parameters
    output_dtype: str = "float32"
    fill_value: float = 0.0

    _ALLOWED_DTYPES: ClassVar[frozenset[str]] = frozenset({
        "float16", "float32", "float64", "int32", "int64",
    })

    def __post_init__(self) -> None:
        if not self.features:
            err_msg = "features must be non-empty"
            logger.error(err_msg)
            raise ValueError(err_msg)
        names = [f.name for f in self.features]
        if len(names) != len(set(names)):
            dupes = sorted({n for n in names if names.count(n) > 1})
            err_msg = f"duplicate feature names: {dupes}"
            logger.error(err_msg)
            raise ValueError(err_msg)
        if self.output_dtype not in self._ALLOWED_DTYPES:
            err_msg = (
                f"output_dtype must be one of "
                f"{sorted(self._ALLOWED_DTYPES)}, "
                f"got {self.output_dtype!r}"
            )
            logger.error(err_msg)
            raise ValueError(err_msg)
        # source_path is validated at compile time (FileNotFoundError),
        # not at config construction time — the file may not exist yet.
