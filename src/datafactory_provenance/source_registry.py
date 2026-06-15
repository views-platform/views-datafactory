"""Source registry — single source of truth for pipeline sources.

Every data source in the pipeline is declared here as a SourceEntry.
Consumers (health checks, pre-flight validation, assembly, remote
verification) import from this module instead of maintaining their
own hardcoded lists. Adding or removing a source is a one-entry
change. ADR-003 (declarations over inference), ADR-009 (boundary
contracts).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "PIPELINE_SOURCES",
    "SourceEntry",
    "get_all_features",
    "get_required_env_vars",
    "get_source_slo",
    "validate_preflight",
]


@dataclass(frozen=True)
class SourceEntry:
    """A declared pipeline data source.

    Fields
    ------
    name : str
        Human-readable source name (must be unique across the registry).
    required_env_vars : tuple[str, ...]
        Environment variables that must be set for this source to run.
    features : tuple[str, ...]
        Feature names this source contributes to the assembled grid.
        Empty for sources that don't produce grid features directly
        (e.g. downstream layers like Consolidation).
    slo_hours : int | None
        Maximum acceptable age in hours before data is stale.
        None means static (never stale from age alone).
    ledger_path : Path | None
        Path to the provenance ledger relative to the provenance
        root directory (e.g. ``ucdp_annual/ingestion_ledger.jsonl``,
        not ``provenance/ucdp_annual/...``). Health scripts prepend
        their ``--provenance-dir`` argument.
    """

    name: str
    required_env_vars: tuple[str, ...] = ()
    features: tuple[str, ...] = ()
    slo_hours: int | None = None
    ledger_path: Path | None = None

    def __post_init__(self) -> None:
        if not self.name:
            msg = "SourceEntry.name must be non-empty"
            raise ValueError(msg)
        for var in self.required_env_vars:
            if not var:
                msg = "required_env_vars must not contain empty strings"
                raise ValueError(msg)
        for feat in self.features:
            if not feat:
                msg = "features must not contain empty strings"
                raise ValueError(msg)
        if self.slo_hours is not None and self.slo_hours <= 0:
            msg = f"slo_hours must be positive, got {self.slo_hours}"
            raise ValueError(msg)


PIPELINE_SOURCES: tuple[SourceEntry, ...] = (
    # ── Harvest layer (raw data ingestion) ──
    SourceEntry(
        name="UCDP Annual",
        required_env_vars=("UCDP_API_TOKEN",),
        features=(
            "ged_sb_count", "ged_sb_best",
            "ged_ns_count", "ged_ns_best",
            "ged_os_count", "ged_os_best",
        ),
        slo_hours=8760,
        ledger_path=Path(
            "ucdp_annual/ingestion_ledger.jsonl"
        ),
    ),
    SourceEntry(
        name="UCDP Candidate",
        required_env_vars=("UCDP_API_TOKEN",),
        slo_hours=744,
        ledger_path=Path(
            "ucdp_candidate/ingestion_ledger.jsonl"
        ),
    ),
    SourceEntry(
        name="UCDP .9",
        required_env_vars=("UCDP_API_TOKEN",),
        slo_hours=744,
        ledger_path=Path(
            "ucdp_dot9/ingestion_ledger.jsonl"
        ),
    ),
    SourceEntry(
        name="ACLED",
        required_env_vars=("ACLED_USERNAME", "ACLED_PASSWORD"),
        features=(
            "acled_count", "acled_battles",
            "acled_explosions", "acled_vac",
            "acled_protests", "acled_riots",
            "acled_strategic", "acled_fatalities",
        ),
        slo_hours=744,
        ledger_path=Path(
            "acled/ingestion_ledger.jsonl"
        ),
    ),
    SourceEntry(
        name="GHS-POP",
        features=(
            "ghspop_pop_count",
        ),
        slo_hours=None,
        ledger_path=Path(
            "ghspop/ingestion_ledger.jsonl"
        ),
    ),
    SourceEntry(
        name="GHS-BUILT-S",
        features=(
            "ghsbuilts_built_area",
        ),
        slo_hours=None,
        ledger_path=Path(
            "ghsbuilts/ingestion_ledger.jsonl"
        ),
    ),
    SourceEntry(
        name="PRIO-GRID Static",
        features=(
            "agri_gc", "aquaveg_gc", "barren_gc",
            "cmr_max", "cmr_mean", "cmr_min", "cmr_sd",
            "diamprim_s", "diamsec_s",
            "forest_gc", "gem_s",
            "goldplacer_s", "goldsurface_s", "goldvein_s",
            "growend", "growstart", "harvarea",
            "herb_gc",
            "imr_max", "imr_mean", "imr_min", "imr_sd",
            "landarea", "maincrop", "mountains_mean",
            "petroleum_s", "rainseas",
            "shrub_gc",
            "ttime_max", "ttime_mean", "ttime_min", "ttime_sd",
            "urban_gc", "water_gc",
        ),
        slo_hours=None,
        ledger_path=Path(
            "priogrid_static/ingestion_ledger.jsonl"
        ),
    ),
    SourceEntry(
        name="V-Dem",
        features=(
            "vdem_v2xcl_dmove",
            "vdem_v2xeg_eqdr",
            "vdem_v2xpe_exlsocgr",
            "vdem_v2x_clphy",
            "vdem_v2xcl_prpty",
            "vdem_v2x_ex_military",
            "vdem_v2x_ex_party",
            "vdem_v2x_horacc",
            "vdem_v2xnp_client",
            "vdem_v2xnp_regcorr",
            "vdem_v2xpe_exlgeo",
            "vdem_v2x_veracc",
            "vdem_v2xpe_exlpol",
            "vdem_v2x_diagacc",
            "vdem_v2x_divparctrl",
            "vdem_v2xeg_eqprotec",
            "vdem_v2x_genpp",
            "vdem_v2xpe_exlgender",
            "vdem_v2x_hosabort",
            "vdem_v2x_libdem",
            "vdem_v2xcl_rol",
            "vdem_v2x_accountability",
        ),
        slo_hours=None,
        ledger_path=Path(
            "vdem/ingestion_ledger.jsonl"
        ),
    ),
    SourceEntry(
        name="SHDI",
        required_env_vars=("GDL_API_TOKEN",),
        features=(
            "shdi_shdi", "shdi_healthindex",
            "shdi_edindex", "shdi_incindex",
        ),
        slo_hours=None,
        ledger_path=Path(
            "shdi/ingestion_ledger.jsonl"
        ),
    ),
    SourceEntry(
        name="PRIO-GRID Shapefile",
        slo_hours=None,
        ledger_path=Path(
            "priogrid/ingestion_ledger.jsonl"
        ),
    ),
    SourceEntry(
        name="GAUL Admin",
        features=(
            "gaul0_code", "gaul1_code", "gaul2_code",
        ),
        slo_hours=None,
        # No ledger_path: GAUL admin boundaries are static shapefiles
        # read directly by assemble_grid.py, not harvested via a
        # provenance-tracked ingestion pipeline.
    ),
    # ── Downstream layers ──
    SourceEntry(
        name="Consolidation",
        slo_hours=744,
        ledger_path=Path(
            "consolidation/ledger.jsonl"
        ),
    ),
    SourceEntry(
        name="ACLED Consolidation",
        slo_hours=744,
        ledger_path=Path(
            "consolidation/acled_ledger.jsonl"
        ),
    ),
    SourceEntry(
        name="Viewpoint",
        slo_hours=744,
        ledger_path=Path(
            "viewpoint/ledger.jsonl"
        ),
    ),
    SourceEntry(
        name="ACLED Viewpoint",
        slo_hours=744,
        ledger_path=Path(
            "viewpoint/acled_v1_ledger.jsonl"
        ),
    ),
    SourceEntry(
        name="GHS-POP Viewpoint",
        slo_hours=None,
        ledger_path=Path(
            "viewpoint/ghspop_v1_ledger.jsonl"
        ),
    ),
    SourceEntry(
        name="GHS-BUILT-S Viewpoint",
        slo_hours=None,
        ledger_path=Path(
            "viewpoint/ghsbuilts_v1_ledger.jsonl"
        ),
    ),
    SourceEntry(
        name="V-Dem Viewpoint",
        slo_hours=None,
        ledger_path=Path(
            "viewpoint/vdem_v1_ledger.jsonl"
        ),
    ),
    SourceEntry(
        name="SHDI Viewpoint",
        slo_hours=None,
        ledger_path=Path(
            "viewpoint/shdi_v1_ledger.jsonl"
        ),
    ),
    SourceEntry(
        name="Compilation",
        slo_hours=744,
        ledger_path=Path(
            "compilation/ledger.jsonl"
        ),
    ),
    SourceEntry(
        name="ACLED Compilation",
        slo_hours=744,
        ledger_path=Path(
            "compilation/acled_ledger.jsonl"
        ),
    ),
    SourceEntry(
        name="GHS-POP Compilation",
        slo_hours=None,
        ledger_path=Path(
            "compilation/ghspop_ledger.jsonl"
        ),
    ),
    SourceEntry(
        name="GHS-BUILT-S Compilation",
        slo_hours=None,
        ledger_path=Path(
            "compilation/ghsbuilts_ledger.jsonl"
        ),
    ),
    SourceEntry(
        name="V-Dem Compilation",
        slo_hours=None,
        ledger_path=Path(
            "compilation/vdem_ledger.jsonl"
        ),
    ),
    SourceEntry(
        name="SHDI Compilation",
        slo_hours=None,
        ledger_path=Path(
            "compilation/shdi_ledger.jsonl"
        ),
    ),
)


def get_source_slo(
    sources: tuple[SourceEntry, ...] = PIPELINE_SOURCES,
) -> dict[str, int | None]:
    """Build name → SLO-hours mapping from the registry."""
    return {s.name: s.slo_hours for s in sources}


def get_all_features(
    sources: tuple[SourceEntry, ...] = PIPELINE_SOURCES,
) -> tuple[str, ...]:
    """Ordered feature tuple from all sources that declare features."""
    result: list[str] = []
    for s in sources:
        result.extend(s.features)
    return tuple(result)


def get_required_env_vars(
    sources: tuple[SourceEntry, ...] = PIPELINE_SOURCES,
) -> set[str]:
    """Union of all required environment variables."""
    result: set[str] = set()
    for s in sources:
        result.update(s.required_env_vars)
    return result


def validate_preflight(
    sources: tuple[SourceEntry, ...] = PIPELINE_SOURCES,
) -> list[dict[str, str]]:
    """Validate all source prerequisites.

    Checks that required environment variables are set and non-empty.
    Returns a list of {name, source, status, detail} dicts. Status
    is "OK" or "FAIL". The ``source`` field names the first
    SourceEntry that requires this variable.
    """
    results: list[dict[str, str]] = []
    seen_vars: set[str] = set()

    for source in sources:
        for var in source.required_env_vars:
            if var in seen_vars:
                continue
            seen_vars.add(var)
            value = os.environ.get(var, "")
            if value:
                results.append({
                    "name": var,
                    "source": source.name,
                    "status": "OK",
                    "detail": "set",
                })
            else:
                results.append({
                    "name": var,
                    "source": source.name,
                    "status": "FAIL",
                    "detail": (
                        f"not set — add to ~/.profile: "
                        f"export {var}=\"...\""
                    ),
                })

    return results
