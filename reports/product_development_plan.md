# Product Development Plan

**Repository:** views-datafactory
**Date:** 2026-03-16
**Status:** Living document

---

## 1. Product Vision

**views-datafactory** is the data foundation for the VIEWS conflict forecasting platform. It provides:

- Auditable, provenance-tracked ingestion of conflict event data from multiple providers
- A validated spatiotemporal grid (PRIO-GRID) as a shared coordinate system
- Deterministic compilation of raw data onto that grid in consumer-specified formats
- Synthetic data generation with controllable statistical properties for development and testing

The system is designed as a **graph of independent nodes** connected by typed edges. Source nodes (harvesters, generators) produce data. Compilation edges transform it into consumer-specific formats. Consumer nodes read the output. This architecture ensures that adding a new source or a new output format never requires changing existing nodes.

**Value proposition:** Any VIEWS consumer can get conflict data — authentic or synthetic — in the format they need, with full provenance from source to output, without understanding the ingestion or compilation internals.

---

## 2. Users & Stakeholders

### Primary User (now)
**The VIEWS Metric Lab** — a research environment for evaluating forecasting metrics, baseline models, loss functions, and DL architectures. Needs compiled grid data (npy) as input to ExperimentFrame-based evaluation pipelines.

### Future Users
- **views-hydranet** — production neural forecasting models. Will consume compiled grids for training and inference.
- **views-pipeline-core** — central pipeline infrastructure. May depend on the data factory for standardised data access.
- **views-evaluation** — evaluation metrics. May consume compiled grids for benchmarking.
- **VIEWS researchers** — individuals exploring new data sources, features, or modeling approaches. Need easy access to compiled data with clear provenance.

### Stakeholders
- **OCHA / FAO** — downstream consumers of VIEWS forecasts. Do not interact with the data factory directly, but the quality and auditability of the data foundation affects the credibility of forecasts they receive.

---

## 3. Use Cases

**UC-1: Harvest latest UCDP data.**
A researcher runs the harvester. It fetches the latest annual and candidate monthly data from UCDP, validates schema and domain constraints, stores raw Parquet snapshots, appends provenance ledger entries, and generates audit reports. If the data hasn't changed (digest match), it records a heartbeat and skips expensive reporting.

**UC-2: Compile authentic data to grid.**
A researcher runs the compiler. It reads raw Parquet snapshots (produced by UC-1), the grid definition, and a compilation config (specifying features and aggregation strategy). It produces a npy file with shape `(n_cells, n_steps, n_features)` plus coordinate arrays (pgids, time_steps, feature_names). It writes a provenance entry linking the output to the specific source snapshots and config used.

**UC-3: Generate synthetic data.**
A researcher configures a synthetic generator (covariance parameters, seed, statistical profile). The generator produces a npy file with the same shape and coordinate metadata as the authentic compiled grid. Provenance records: config hash + seed + generator version.

**UC-4: Add a new data source.**
A developer adds a new module in `harvester/sources/` with source-specific API client and schema contract. The shared harvester skeleton (fetch → validate → store → provenance) handles the rest. No changes to existing sources, the grid, or the compiler.

**UC-5: Compile to a different format.**
A future consumer needs panel/parquet instead of grid npy. A new compilation edge is added (a new module or config option in the compiler) without changing the harvester or the grid.

**UC-6: Trace a value back to its source.**
An analyst sees an anomalous value in cell 142,301 at month 2024-06. They consult the compilation provenance (which source snapshots + config produced this grid). They find the relevant Parquet snapshot, filter to that cell's `priogrid_gid` and month, and see the specific UCDP events. The provenance chain is: compiled npy → compilation ledger → source Parquet → harvester ledger → UCDP API response.

---

## 4. Product Requirements

### Functional

| ID | Requirement | Priority |
|----|-------------|----------|
| F-1 | Harvest UCDP/GED annual data with schema validation and provenance | Done (DoD003) |
| F-2 | Harvest UCDP/GED candidate monthly data with revision tracking | Done in metric lab; candidate source not yet migrated to this repo |
| F-3 | Generate PRIO-GRID spatial backbone (259,200 cells, 0.5°) | Done (DoD002) |
| F-4 | Generate temporal backbone (monthly, 1989-2024) with VIEWS month_id adapter | Done (DoD002) |
| F-5 | Compile harvested events onto spatiotemporal grid as npy | Done (DoD004) |
| F-6 | Generate synthetic grid data with controllable covariance | Next |
| F-7 | Track provenance through compilation (source digests + config → output digest) | Done (DoD004) |
| F-8 | Support pluggable aggregation strategies in compilation | Done (DoD004 — count, sum_best, max_best) |
| F-9 | Add second data source (ACLED or PRIO static variables) | Future |
| F-10 | Support zarr output format alongside npy | Future |

### Non-Functional

| ID | Requirement |
|----|-------------|
| NF-1 | **Auditability**: Every compiled output traceable to source records via provenance chain |
| NF-2 | **Reproducibility**: Same inputs + same config = bit-identical output (deterministic compilation) |
| NF-3 | **Fail-loud**: Invalid configs, schema violations, and integrity failures raise exceptions. No silent fallbacks. |
| NF-4 | **Independence**: Source nodes have zero imports from each other or from compilation/consumer code |
| NF-5 | **Performance**: Full grid compilation (259,200 cells × 432 months) completes in under 60 seconds |
| NF-6 | **Minimal dependencies**: Core grid and compilation depend only on numpy. Harvesters add requests + pyarrow. No heavy geospatial libraries. |

---

## 5. System Architecture

```
┌─────────────────────────────────────────────────┐
│                  views-datafactory               │
│                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐   │
│  │   core   │  │   grid   │  │  harvester   │   │
│  │----------│  │----------│  │--------------│   │
│  │provenance│  │ spatial  │  │  sources/    │   │
│  │ configs  │  │ temporal │  │   ucdp_ann   │   │
│  │          │  │ composed │  │   ucdp_cand  │   │
│  └──────────┘  └──────────┘  │   (future)   │   │
│       ↑             ↑        └──────────────┘   │
│       │             │               │            │
│       │        ┌────┴───────────────┘            │
│       │        │                                 │
│  ┌────┴────────┴──┐       ┌──────────────┐      │
│  │    compiler    │       │  synthetic   │      │
│  │----------------│       │--------------│      │
│  │ events → grid  │       │ grid-native  │      │
│  │ npy output     │       │ covariance   │      │
│  │ provenance     │       │ generation   │      │
│  └────────────────┘       └──────────────┘      │
│                                                  │
└─────────────────────────────────────────────────┘
         │                         │
         ▼                         ▼
   ┌───────────┐            ┌───────────┐
   │ compiled  │            │ synthetic │
   │ grid.npy  │            │ grid.npy  │
   └───────────┘            └───────────┘
         │                         │
         └────────┬────────────────┘
                  ▼
         ┌────────────────┐
         │  metric lab    │
         │  (consumer)    │
         └────────────────┘
```

**Dependency rules:**
- `datafactory_core` imports nothing internal
- `datafactory_grid`, `datafactory_harvester`, `datafactory_synthetic` import only from `datafactory_core`
- `datafactory_compiler` imports from `datafactory_core` and `datafactory_grid` (for coordinates); reads harvester/synthetic outputs as **files**, not code imports
- No package imports from the compiler or from consumers
- Independence is enforced by the filesystem: each `datafactory_*` is a separate top-level package

---

## 6. Data Infrastructure

### 6.1 Raw Data Storage

**Format:** Apache Parquet (columnar, compressed, preserves all source fields)
**Location:** `data/` (gitignored — disposable cache, rebuildable from provenance)
**Naming:** `data/{source}/{version}/snapshot.parquet`

Each Parquet file is a verbatim copy of the API response at fetch time. No fields are dropped, renamed, or transformed. The harvester stores what it receives.

### 6.2 Compiled Data Storage

**Format:** npy (numpy `.npy` files with sidecar coordinate arrays)
**Location:** `data/compiled/{config_hash}/`
**Contents:**
- `grid.npy` — shape `(n_cells, n_steps, n_features)`, dtype float32
- `pgids.npy` — shape `(n_cells,)`, dtype int32
- `time_steps.npy` — shape `(n_steps,)`, dtype datetime64[M]
- `feature_names.json` — list of feature names matching the feature axis
- `provenance.json` — source digests, compilation config, output digest

**Contract:** Dimension order is always (cells, time, features). Coordinate arrays are always shipped alongside the data array. This is the zarr-ready contract — when we switch to zarr, the structure maps directly to zarr dimensions and coordinates.

### 6.3 Provenance

**Format:** JSONL (append-only, one entry per operation)
**Location:** `provenance/` (tracked in git — survives data cache deletion)
**Ledger files:**
- `provenance/harvester_ledger.jsonl` — one entry per harvest operation
- `provenance/compiler_ledger.jsonl` — one entry per compilation
- `provenance/synthetic_ledger.jsonl` — one entry per generation

Each entry contains: timestamp, operation type, input references (source paths + digests), config snapshot, output path + digest, validation results.

### 6.4 Validation

Validation happens at every boundary:
- **Harvest time:** Schema validation (required fields, types, bounds), domain validation (date ranges, coordinate bounds), integrity validation (digest computation)
- **Compilation time:** Input validation (source Parquet exists and matches expected digest), output validation (grid dimensions match config, no NaN in unexpected places, coordinate arrays match)
- **Synthetic generation:** Config validation (positive variances, valid correlation ranges), output validation (same as compilation)

---

## 7. Model Operationalization

Not applicable to the data factory. Model training, inference, and deployment are concerns of the metric lab and views-hydranet. The data factory's responsibility ends at producing compiled grid files that models can consume.

The interface contract between the data factory and model consumers is the **compiled grid format** (section 6.2): a npy array with shape `(n_cells, n_steps, n_features)` plus coordinate metadata.

---

## 8. Interfaces

### 8.1 Python API

```python
# Harvesting
from datafactory_harvester.sources.ucdp_annual import fetch_ucdp_annual, UcdpAnnualConfig
fetch_ucdp_annual(UcdpAnnualConfig())  # fetches, validates, stores, logs provenance

# Or via registry:
from datafactory_harvester.sources import fetch_source
import datafactory_harvester.sources.ucdp_annual  # auto-registers
fetch_source("ucdp_annual", config=UcdpAnnualConfig())

# Grid
from datafactory_grid import GridConfig, SpatioTemporalGrid
grid = SpatioTemporalGrid()   # default: 259,200 cells × 432 months

# Compilation
from datafactory_compiler import CompilationConfig, compile_grid
config = CompilationConfig(
    source_path=Path("data/ucdp_annual/snapshot.parquet"),
    features=(("event_count", "count"), ("fatalities", "sum_best")),
)
compile_grid(config)  # produces grid.npy + sidecars + provenance

# Synthetic (not yet implemented)
# from datafactory_synthetic import generate_synthetic
# generate_synthetic(grid=grid, config=..., seed=42)
```

### 8.2 Audit Reports

Each harvest and compilation produces human-readable Markdown + PNG reports in `reports/`. These include:
- Data quality summaries (completeness, schema compliance, distributional statistics)
- Comparison with previous runs (what changed, revision tracking)
- Provenance summary (which sources, which config, output digest)

### 8.3 Provenance Query

The provenance ledgers are queryable JSONL files. A future convenience function may provide:
```python
from datafactory_core.provenance import trace
trace("data/compiled/abc123/grid.npy")
# Returns: source snapshots, compilation config, timestamps
```

---

## 9. Release Plan

### MVP (complete)
- [x] Repository scaffold with package structure, tooling, CI config
- [x] Core provenance utilities (DoD001 — `03517eb`)
- [x] Grid module (DoD002 — `da1f7c4`)
- [x] Harvester module with UCDP annual source (DoD003 — `fc0953f`)
- [x] First compiled grid — compiler with pluggable strategies (DoD004 — `9cd8536`)

### v0.2: Synthetic Generation
- [ ] Grid-native synthetic generator with spatial + temporal covariance
- [ ] Synthetic provenance (config hash + seed + version)
- [ ] Statistical profile of authentic data (calibration target)

### v0.3: Multi-Source
- [ ] Second data source (ACLED or PRIO static variables)
- [ ] Multi-source compilation
- [ ] Fidelity validation node (synthetic vs. authentic comparison)

### v0.4: Format Expansion
- [ ] Zarr output format
- [ ] Panel/Parquet compilation edge
- [ ] Compilation uncertainty propagation (source precision → cell-level uncertainty)

### Future
- Package publication (PyPI or private index) — when other VIEWS repos need to depend on it
- Relational DB and graph DB compilation edges — when consumers request them

---

## 10. Operations & Maintenance

### 10.1 Data Freshness

UCDP releases candidate monthly data on a rolling basis. The harvester should run periodically (monthly at minimum) to capture new releases. The digest-based short-circuit ensures that unchanged data doesn't trigger expensive reprocessing.

When UCDP releases a new annual version (e.g., v26.1), the harvester config needs updating (new version ID, extended year range). This is a config change, not a code change.

### 10.2 Schema Drift

UCDP may add, remove, or rename fields between versions. The harvester's schema validation detects this immediately (fail-loud on missing required fields). The response is manual: update the schema contract in the source module, assess impact on compilation, update audit reports.

### 10.3 Dependency Updates

Dependencies are version-constrained (major version pins). `uv lock` ensures reproducible installs. Dependabot or manual review for security patches.

### 10.4 Provenance Integrity

Provenance ledgers are append-only and tracked in git. If a ledger becomes corrupted, git history provides the authoritative record. Compiled outputs can always be rebuilt from raw data + provenance.

---

## 11. Adoption & Impact

### 11.1 Metric Lab Integration

The metric lab is the first consumer. Integration path:
1. Add `views-datafactory` as a dependency in the lab's `pyproject.toml`
2. Update lab imports: `from datafactory_grid import GridConfig, SpatioTemporalGrid`
3. Replace lab's local grid/harvester code with data factory imports
4. Lab continues to own: ExperimentFrame, evaluation metrics, models, loss functions

### 11.2 Broader VIEWS Ecosystem

As the data factory matures, other VIEWS repos can depend on it for:
- Standardised grid definitions (everyone uses the same cell IDs and coordinate system)
- Shared data access (one harvester, multiple consumers)
- Reproducible data (provenance ensures everyone works from the same source)

### 11.3 Feedback Loops

- **From metric lab:** Which aggregation strategies produce the best downstream model performance? (Informs compiler development.)
- **From modelers:** What features and temporal resolution do they need? (Informs source expansion.)
- **From stakeholders (OCHA/FAO):** What data quality and freshness guarantees do they require? (Informs operational requirements.)
