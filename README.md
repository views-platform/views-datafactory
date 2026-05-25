<div style="width: 100%; max-width: 1500px; height: 400px; overflow: hidden; position: relative;">
  <img src="https://github.com/user-attachments/assets/1ec9e217-508d-4b10-a41a-08dface269c7" alt="VIEWS Twitter Header" style="position: absolute; top: -50px; width: 100%; height: auto;">
</div>

# views-datafactory

**Data factory for the VIEWS conflict forecasting platform — harvesting, consolidation, viewpoint building, grid compilation, and query.**

Part of the [VIEWS Platform](https://github.com/views-platform) ecosystem.

---

## Table of Contents

- [Overview](#overview)
- [Role in VIEWS Platform](#role-in-views-platform)
- [Architecture](#architecture)
- [Packages](#packages)
- [Project Structure](#project-structure)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Strategic Documents](#strategic-documents)
- [Where to Find What](#where-to-find-what)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

views-datafactory provides the data foundation for conflict forecasting in the VIEWS platform. It handles the full lifecycle of spatiotemporal conflict data — from raw ingestion through to compiled grid arrays ready for model consumption.

The system is designed as a **graph of independent nodes**, not a linear pipeline. Source nodes (harvesters) produce data independently. Compilation edges transform source data into consumer-specific formats. Consumer nodes read compiled outputs. This architecture ensures that adding a new data source or output format never requires changing existing components.

### Key Capabilities

- **Auditable data harvesting** — UCDP (annual, candidate, .9), ACLED, GHS-POP, GHS-BUILT-S, PRIO-GRID static, and GAUL admin boundaries, all with schema validation, drift detection, and JSONL provenance ledgers
- **PRIO-GRID spatial backbone** — pure-numpy generation of the standard 259,200-cell global grid at 0.5° resolution, validated cell-by-cell against the official PRIO reference shapefile
- **Temporal backbone** with VIEWS month_id adapters (epoch: January 1980)
- **Vintage-aware consolidation** — lossless, append-only, bitemporal event store from all three UCDP sources with content-digest deduplication
- **Configurable viewpoints** — survivorship strategies (annual_wins, dot9_wins), temporal distribution (even_split, ceil_split), production filtering via named profiles
- **Deterministic compilation** of viewpoint output onto the spatiotemporal grid as npy arrays
- **Consumer adapters** — grid-to-DataFrame and grid-to-FeatureFrame conversions for downstream consumers
- **End-to-end provenance** — every value in a compiled grid is traceable back to the specific source records and compilation config that produced it

---

## Role in VIEWS Platform

views-datafactory is the upstream data provider for the VIEWS forecasting pipeline. It produces the compiled grid arrays that models consume for training and inference.

### Integration with Other Repositories

- **[views-metric-lab](https://github.com/views-platform/views-metric-lab):** First consumer — uses compiled grids for evaluation metric research and model stress-testing
- **[views-hydranet](https://github.com/views-platform/views-hydranet):** Will consume compiled grids for production neural forecasting (HydraNet v2)
- **[views-pipeline-core](https://github.com/views-platform/views-pipeline-core):** Central pipeline infrastructure — may depend on views-datafactory for standardised data access
- **[views-evaluation](https://github.com/views-platform/views-evaluation):** May consume compiled grids for benchmarking

### Data Flow

**No layer imports from the layer above or below.** The filesystem is the API between layers. Each dashed line below represents zero code coupling — only a file path convention. This is enforced by an import-enforcement test that AST-scans every package.

```
UCDP/GED API ──→ datafactory_harvester ──→ data/raw/ucdp_*/*.parquet
ACLED API ──────→ datafactory_harvester ──→ data/raw/acled/*.parquet
                    (event sources)
                                         ─ ─ ─ ─ ─ ─ ─ ─  filesystem boundary
                                              │
                                  datafactory_consolidation ──→ data/consolidated/*.parquet
                                              │
                                         ─ ─ ─ ─ ─ ─ ─ ─  filesystem boundary
                                              │
                                  datafactory_viewpoint ──→ data/viewpoint/*.parquet
                                              │
                                         ─ ─ ─ ─ ─ ─ ─ ─  filesystem boundary
                                              │
PRIO-GRID ──────→ datafactory_priogrid ─┐     │
PRIO-GRID API ──→ datafactory_harvester ──→ data/raw/priogrid_static/
FAO GAUL API ───→ datafactory_harvester ──→ data/raw/gaul_admin/
JRC GHSL ───────→ datafactory_harvester ──→ data/raw/ghspop/ + ghsbuilts/
                    (GHS-POP, GHS-BUILT-S skip consolidation — single releases)
                                        │     │
                                  datafactory_compilation ──→ data/compiled/grid.npy [T,H,W,C]
                                              │
                                         ─ ─ ─ ─ ─ ─ ─ ─  filesystem boundary
                                              │
                                  assemble_grid.py ──→ data/assembled/grid.npy [T,H,W,F]
                                     (compiled UCDP + ACLED + GHS-POP + GHS-BUILT-S + static + admin)
                                              │
                                         ─ ─ ─ ─ ─ ─ ─ ─  filesystem boundary
                                              │
                                  datafactory_query ──→ FeatureFrame / DataFrame
                                     (load_dataset: region, time, feature subsetting)
                                              │
                                  generate_consumer_data.py ──→ {run_type}_viewser_df.parquet
                                     (factory → VIEWSER vocabulary)
                                              │
                                  ┌───────────┴───────────┐
                                  │      Consumers        │
                                  │  (metric lab,         │
                                  │   hydranet)           │
                                  └───────────────────────┘

```

Not all paths traverse all layers. GHS-POP and GHS-BUILT-S skip consolidation (single releases; ADR-029, ADR-034).

---

## Architecture

The architecture is a **graph**, not a pipeline. Each node is a self-contained package with explicit dependencies:

```
Layer 0 — Foundation (no internal imports):
  datafactory_provenance        Content digests, JSONL ledger operations
  datafactory_http              HTTP request utilities: retry with exponential backoff

Layer 1 — Source nodes (import provenance + http):
  datafactory_priogrid          PRIO-GRID spatial + temporal backbone
  datafactory_harvester         Data ingestion with pluggable sources

Layer 2 — Consolidation (imports provenance, reads harvester files):
  datafactory_consolidation     Lossless event store from raw snapshots

Layer 3 — Viewpoint (imports provenance, reads consolidation files):
  datafactory_viewpoint         Opinionated materialized views

Layer 4 — Compilation (imports provenance + priogrid, reads viewpoint files):
  datafactory_compilation       Viewpoint output → populated grid arrays

Consumer-facing (no datafactory_* imports):
  datafactory_adapters          Grid → DataFrame, Grid → FeatureFrame

Assembly (script, not package — combines compiled sources):
  scripts/assemble_grid.py      Compiled UCDP + ACLED + GHS-POP + GHS-BUILT-S + static + admin → [T,H,W,F]

Consumer entry point (imports priogrid + adapters, reads assembled files):
  datafactory_query             load_dataset() — region/time/feature subsetting, npy or zarr
```

**Dependency rules (ADR-012):**
- `datafactory_provenance` imports nothing internal
- `datafactory_priogrid` and `datafactory_harvester` import only from `datafactory_provenance` (and `datafactory_http` for network operations)
- `datafactory_consolidation` imports only from `datafactory_provenance`; reads harvester output as **files**
- `datafactory_viewpoint` imports only from `datafactory_provenance`; reads consolidation output as **files**
- `datafactory_compilation` imports `datafactory_provenance` and `datafactory_priogrid`; reads viewpoint output as **files**
- `datafactory_adapters` imports nothing from `datafactory_*`; sits alongside the graph, not inside it
- `datafactory_query` imports `datafactory_priogrid` and `datafactory_adapters`; reads assembled output as **files** (npy or zarr)
- Independence is enforced by an import-enforcement test that AST-scans every package

### Design Principles

| Principle | Description |
|-----------|-------------|
| **Graph, not pipeline** | Sources don't know about consumers. Compilation edges are consumer-driven. |
| **Provenance all the way through** | Every node that produces data writes a JSONL ledger entry. Mission-critical. |
| **Config-driven, fail-loud** | Frozen dataclasses with `__post_init__` validation. No silent defaults. |
| **npy now, zarr-ready** | Dimension order: `(cells, time, features)`. Coordinate arrays shipped alongside data. |
| **Screaming architecture** | Package and file names communicate domain, not programming taxonomy. |

### Filesystem Boundaries and Data Contracts

Layers are decoupled by the filesystem, not by imports. Each layer computes SHA-256 of its input file (`source_digest`) and output file (`output_digest`), recording both in its JSONL ledger. This creates a cryptographic provenance chain from raw API response to consumer parquet — any tampering or re-run is detectable by comparing digests across ledgers.

| Boundary | Writer | Reader | File Path | Format | Key Columns / Shape |
|----------|--------|--------|-----------|--------|---------------------|
| Harvest → Consolidation | `harvest_ucdp.py` | `consolidate_ucdp.py` | `data/raw/ucdp_*/` | Parquet | `id`, `date_start`, `date_end`, `best`, `low`, `high`, `type_of_violence` |
| Consolidation → Viewpoint | `consolidate_ucdp.py` | `build_viewpoint.py` | `data/consolidated/` | Parquet | All harvest columns + `_source_type`, `_source_version`, `_ingested_at` |
| Viewpoint → Compilation | `build_viewpoint.py` | `compile_grid.py` | `data/viewpoint/*.parquet` | Parquet | `latitude`, `longitude`, `date_month`, `best`, `type_of_violence` |
| Compilation → Assembly | `compile_grid.py` | `assemble_grid.py` | `data/compiled/` | npy `[T,H,W,C]` | `grid.npy` + `pgids.npy` + `time_steps.npy` + `feature_names.json` |
| Assembly → Query/Consumer | `assemble_grid.py` | `load_dataset()` | `data/assembled/` or `.zarr` | npy or zarr | `grid.npy [T,H,W,F]` with same sidecars |

### Consumer Contract

The `generate_consumer_data.py` script bridges factory vocabulary to the format expected by VIEWS training scripts (`purple_alien`, `white_ranger`, etc.):

| Factory column | Consumer column | Meaning |
|----------------|----------------|---------|
| `ged_sb_best` | `lr_sb_best` | State-based conflict fatalities (best estimate) |
| `ged_ns_best` | `lr_ns_best` | Non-state conflict fatalities |
| `ged_os_best` | `lr_os_best` | One-sided violence fatalities |
| `gaul0_code` | `c_id` | Country identifier (GAUL Level 0) |
| _(derived)_ | `row`, `col` | Grid position derived from `priogrid_gid` |

Training partitions use VIEWS month_id encoding (epoch: January 1980):
- **Calibration:** train 121–444, test 445–492
- **Validation:** train 121–492, test 493–540
- **Forecasting:** train 121–current, test current+1 to current+36

Output: `{calibration,validation,forecasting}_viewser_df.parquet` with MultiIndex `(month_id, priogrid_gid)`.

---

## Packages

| Package | Layer | Purpose | Status |
|---------|-------|---------|--------|
| `datafactory_provenance` | 0 | Content digests, JSONL ledgers, file locking, rotation | Done |
| `datafactory_http` | 0 | HTTP request utilities: retry with exponential backoff | Done |
| `datafactory_priogrid` | 1 | PRIO-GRID spatial + temporal backbone (259,200 cells, monthly) | Done |
| `datafactory_harvester` | 1 | Data harvesting: UCDP (annual/candidate/.9), ACLED, GHS-POP, GHS-BUILT-S, PRIO-GRID static, GAUL admin | Done |
| `datafactory_consolidation` | 2 | Lossless, vintage-aware consolidation of UCDP and ACLED sources | Done |
| `datafactory_viewpoint` | 3 | Opinionated views: survivorship, temporal distribution, profiles | Done |
| `datafactory_compilation` | 4 | Viewpoint output → grid npy with coordinate sidecars | Done |
| `datafactory_adapters` | — | Consumer-facing: grid → DataFrame, grid → FeatureFrame | Done |
| `datafactory_query` | — | Consumer entry point: `load_dataset()`, region/time subsetting, dual npy/zarr backend | Done |

---

## Project Structure

```
views-datafactory/
├── pyproject.toml                                    # hatchling + uv
├── CLAUDE.md                                         # AI assistant context
├── .github/workflows/ci.yml                          # CI: ruff + mypy + pytest
├── src/
│   ├── datafactory_provenance/                       # Layer 0 — digests + ledgers
│   │   ├── digests_and_ledgers.py
│   │   ├── constants.py                                VIEWS_EPOCH_YEAR (shared constant)
│   │   └── source_registry.py                          SourceEntry, PIPELINE_SOURCES
│   ├── datafactory_http/                             # Layer 0 — HTTP retry utilities
│   │   └── retry.py                                    request_with_retry (shared)
│   ├── datafactory_priogrid/                         # Layer 1 — PRIO-GRID backbone
│   │   ├── grid_config.py                              GridConfig (spatial params)
│   │   ├── temporal_config.py                          TemporalConfig (year/month range)
│   │   ├── cell_generator.py                           generate_grid, pgid_to_latlon
│   │   ├── temporal_generator.py                       generate_time_steps, VIEWS month_id
│   │   ├── spatiotemporal.py                           SpatioTemporalGrid (composition)
│   │   ├── parity_validation.py                        validate_parity (vs. reference shapefile)
│   │   ├── shapefile_reader.py                         PyShpReader (pluggable Protocol)
│   │   └── shapefile_harvester.py                      fetch_shapefile (reference data)
│   ├── datafactory_harvester/                        # Layer 1 — data ingestion
│   │   ├── event_validation.py                         ValidationResult, compare_snapshots
│   │   ├── snapshot_storage.py                         save_event_snapshot, archive_snapshot
│   │   └── sources/                                    Source plugin registry
│   │       ├── ucdp_annual.py                            UCDP/GED Annual source
│   │       ├── ucdp_candidate.py                         UCDP/GED Candidate Monthly source
│   │       ├── ucdp_dot9.py                              UCDP/GED .9 Consolidated Monthly
│   │       ├── acled.py                                  ACLED event data (year-by-year)
│   │       ├── ghspop.py                                 GHS-POP R2023A (JRC GHSL raster)
│   │       ├── ghsbuilts.py                              GHS-BUILT-S R2023A (JRC GHSL raster)
│   │       ├── priogrid_static.py                        PRIO-GRID static covariates
│   │       └── gaul_admin.py                             GAUL 2024 admin boundaries
│   ├── datafactory_consolidation/                    # Layer 2 — lossless event stores
│   │   ├── event_store.py                              Append-only Parquet store
│   │   ├── tagging.py                                  tag_table (shared metadata tagging)
│   │   └── consolidators/
│   │       ├── ucdp.py                                   Three-source UCDP consolidation
│   │       └── acled.py                                  ACLED event consolidation
│   ├── datafactory_viewpoint/                        # Layer 3 — opinionated views
│   │   ├── survivorship.py                             Strategy registry (annual_wins, dot9_wins)
│   │   ├── temporal_distribution.py                    Strategy registry (even_split, ceil_split)
│   │   ├── profiles.py                                 Named presets (production_parity)
│   │   ├── raster_io.py                                read_geotiff (shared GeoTIFF reader)
│   │   ├── temporal.py                                 interpolate_temporal (shared interpolation)
│   │   └── builders/
│   │       ├── ucdp_v1.py                                UCDP viewpoint builder
│   │       ├── ghspop_v1.py                              GHS-POP viewpoint builder
│   │       └── ghsbuilts_v1.py                           GHS-BUILT-S viewpoint builder
│   ├── datafactory_compilation/                      # Layer 4 — grid compilation
│   │   ├── compilation_config.py                       CompilationConfig
│   │   ├── grid_compilation.py                         compile_grid (event sources)
│   │   ├── pregridded_compilation.py                   compile_pregridded (raster sources)
│   │   ├── output.py                                   write_compilation_output (shared writer)
│   │   └── aggregation.py                              count, sum_field, max_field strategies
│   ├── datafactory_adapters/                         # Consumer-facing conversions
│   │   ├── feature_frame.py                            FeatureFrame dataclass
│   │   ├── grid_to_dataframe.py                        Grid → pandas DataFrame
│   │   └── grid_from_feature_frame.py                  FeatureFrame → Grid (inverse)
│   └── datafactory_query/                            # Consumer entry point
│       ├── dataset.py                                  load_dataset (npy + zarr backends)
│       ├── regions.py                                  Region name → PRIO-GRID cell set
│       └── temporal.py                                 Flexible time range parsing
├── tests/                                            # 1094 tests
├── scripts/                                          # Operational scripts
│   ├── harvest_ucdp.py                                 UCDP harvest (annual + candidate + .9)
│   ├── harvest_acled.py                                ACLED event harvest (year-by-year)
│   ├── harvest_ghspop.py                               GHS-POP raster harvest (12 epochs)
│   ├── harvest_ghsbuilts.py                            GHS-BUILT-S raster harvest (12 epochs)
│   ├── harvest_priogrid.py                             PRIO-GRID static covariates
│   ├── harvest_shapefile.py                            PRIO-GRID shapefile download
│   ├── harvest_gaul.py                                 GAUL admin boundary harvest + spatial join
│   ├── consolidate_ucdp.py                             Three-source UCDP consolidation
│   ├── build_viewpoint.py                              Viewpoint from profile
│   ├── compile_grid.py                                 Event source grid compilation
│   ├── compile_acled.py                                ACLED grid compilation
│   ├── run_acled_pipeline.py                           ACLED end-to-end pipeline
│   ├── run_ghspop_pipeline.py                          GHS-POP end-to-end pipeline
│   ├── run_ghsbuilts_pipeline.py                       GHS-BUILT-S end-to-end pipeline
│   ├── assemble_grid.py                                UCDP + ACLED + GHS-POP + GHS-BUILT-S + static + admin
│   ├── generate_consumer_data.py                      Factory → VIEWSER parquet for training
│   ├── export_dataframe.py                             Grid → DataFrame export
│   ├── export_zarr.py                                  Grid → zarr store (HTTP-servable)
│   ├── preflight.py                                    Pre-pipeline disk + env checks
│   ├── check_health.py                                 System health check
│   ├── refresh_pipeline.sh                             Full pipeline orchestrator (11 steps)
│   ├── visualize_audit.py                              Data audit visualization
│   └── ...                                             verify_parity, verify_remote, etc.
├── docs/                                             # ADRs, CICs, protocols, standards
│   ├── ADRs/                                           10 constitutional + 25 project-specific
│   ├── CICs/                                           28 active class intent contracts
│   ├── contributor_protocols/                          carbon, silicon, hardened
│   └── standards/                                      logging & observability
├── reports/                                          # Strategic documents + audit outputs
│   ├── rd_roadmap11.md                                 R&D roadmap (v11)
│   ├── product_development_plan11.md                   Product development plan (v11)
│   ├── technical_risk_register.md                      Technical risk register (ADR-020)
│   └── dot9_investigation/                             .9 data stream research findings
├── provenance/                                       # JSONL ledgers (gitignored)
└── data/                                             # Raw + compiled data (gitignored)
```

---

## Installation

```bash
# Clone the repository
git clone https://github.com/views-platform/views-datafactory.git
cd views-datafactory

# Install with uv
uv sync

# Verify
uv run pytest -v
```

> **Note:** This project uses [uv](https://github.com/astral-sh/uv) for dependency management and [hatchling](https://hatch.pypa.io/) as the build backend.

---

## Quick Start

```bash
# Full pipeline (automated): runs all 11 steps end-to-end
bash scripts/refresh_pipeline.sh

# Or run individual steps:
uv run python scripts/harvest_ucdp.py              # fetch all UCDP sources
uv run python scripts/harvest_acled.py             # fetch ACLED events
uv run python scripts/harvest_ghspop.py            # fetch GHS-POP rasters
uv run python scripts/harvest_ghsbuilts.py         # fetch GHS-BUILT-S rasters
uv run python scripts/consolidate_ucdp.py          # three-source UCDP consolidation
uv run python scripts/build_viewpoint.py           # apply production_parity profile
uv run python scripts/compile_grid.py              # UCDP → grid.npy
uv run python scripts/compile_acled.py             # ACLED → grid.npy
uv run python scripts/run_ghspop_pipeline.py       # GHS-POP viewpoint + compile
uv run python scripts/run_ghsbuilts_pipeline.py    # GHS-BUILT-S viewpoint + compile
uv run python scripts/assemble_grid.py             # all compiled sources → assembled grid
uv run python scripts/generate_consumer_data.py    # factory → VIEWSER training parquets

# Visualize the assembled grid
uv run python scripts/visualize_audit.py           # 15 audit plots → reports/audit/

# Export for downstream consumers
uv run python scripts/export_zarr.py               # grid → zarr store (HTTP-servable)
uv run python scripts/export_dataframe.py          # grid → DataFrame CSV
```

```python
# Programmatic usage — load_dataset() is the primary consumer entry point
from datafactory_query import load_dataset

# Load Ethiopia 2020-2024 as FeatureFrame (temporal + geographic subsetting)
ff = load_dataset(region="Ethiopia", start="2020", end="2024")

# Load global land cells as DataFrame
df = load_dataset(region="land", output_format="dataframe")

# Load from remote zarr store
ff = load_dataset(
    region="africa_me",
    start="2020",
    data_dir="http://204.168.219.108/grid.zarr",
)
```

```python
# Low-level access — direct npy loading
from datafactory_adapters import FeatureFrame, grid_to_dataframe
import json, numpy as np

data = np.load("data/assembled/grid.npy", mmap_mode="r")
pgids = np.load("data/assembled/pgids.npy")
time_steps = np.load("data/assembled/time_steps.npy")
feature_names = json.loads(open("data/assembled/feature_names.json").read())

df = grid_to_dataframe(data, pgids, time_steps, feature_names, month_id_epoch=1980)
ff = FeatureFrame.from_grid(data, pgids, time_steps, feature_names)
```

---

## Strategic Documents

The `reports/` directory contains living documents that define the project's direction:

- **[R&D Roadmap](reports/rd_roadmap11.md)** — Research questions, hypotheses, data agenda, milestones. Focuses on what must be *discovered*.
- **[Product Development Plan](reports/product_development_plan11.md)** — Users, requirements, architecture, release plan. Focuses on what must be *built*.
- **[Technical Risk Register](reports/technical_risk_register.md)** — 202 concerns tracked, 114 resolved, 63 open with trigger conditions (ADR-020).
- **[.9 Investigation](reports/dot9_investigation/)** — Empirical findings on UCDP .9 data stream characteristics.

---

## Where to Find What

This system separates information by ownership and change frequency (ADR-003). Different questions have different authoritative sources:

| If you need to know… | Look in… | Why there |
|----------------------|----------|-----------|
| What data sources we use, who publishes them, what license/format/coverage | `docs/sources/` — catalog cards | Upstream facts, rarely change |
| Why we chose a specific source, what alternatives we considered | `docs/ADRs/` — source selection ADRs (028, 029) | One-time decisions |
| How a derived feature is constructed (aggregation, survivorship, distribution) | Viewpoint CICs (`docs/CICs/Viewpoint*.md`) and profile configs (`src/datafactory_viewpoint/profiles.py`) | Volatile — changes as research evolves |
| What SLO, env vars, or feature list a source has | `src/datafactory_provenance/source_registry.py` — `SourceEntry` | Operational config, changes on redeploy |
| Current harvest status, data versions, content digests | `provenance/*.jsonl` ledgers, or run `uv run python scripts/check_health.py` | Volatile state, changes every pipeline run |
| What a config class guarantees | `docs/CICs/` — Class Intent Contracts | Code contracts |
| Why the system is designed this way | `docs/ADRs/` — Architecture Decision Records | Immutable decisions |
| Known technical risks and their status | `reports/technical_risk_register.md` | Living risk tracking |

**Rule of thumb:** if the information changes when *the upstream provider* changes something → catalog card. When *we* make a decision → ADR. When *we redeploy* → code config. When *the pipeline runs* → provenance ledger. When in doubt, the provenance ledger is the most authoritative source for anything operational.

---

## Contributing

Contributions are welcome. Please consult the [VIEWS Platform contributing guidelines](https://github.com/views-platform) before submitting pull requests.

When adding new packages, follow the existing `datafactory_*` naming convention and ensure the new package:
- Has an `__init__.py` with `__all__` defined
- Is listed in `pyproject.toml` under `[tool.hatch.build.targets.wheel] packages`
- Imports only from `datafactory_provenance` (or provenance + priogrid for compilation nodes)
- Has corresponding tests in `tests/`
- Has an `ARCHITECTURE.md` describing purpose, boundaries, and invariants

---

## License

This project is part of the VIEWS Platform. See [LICENSE](LICENSE) for details.

---

## Acknowledgements

Built as part of the [VIEWS](https://viewsforecasting.org/) (Violence & Impacts Early-Warning System) project, providing early warning for conflict to support humanitarian response and prevention.

Data sources:
- **[UCDP/GED](https://ucdp.uu.se/)** — Uppsala Conflict Data Program / Georeferenced Event Dataset
- **[PRIO-GRID](https://grid.prio.org/)** — Peace Research Institute Oslo global grid structure
