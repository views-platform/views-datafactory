# views-datafactory

Data factory for the VIEWS conflict forecasting platform.

## Architecture

The system is a **graph, not a pipeline** (ADR-012). Layers are decoupled by the filesystem, not by imports. No layer imports from the layer above or below it — data flows as files on disk, and each layer reads/writes independently:
- **Source nodes** (`datafactory_harvester`, `datafactory_synthetic`) produce raw data independently → `data/raw/`
- **Consolidation** (`datafactory_consolidation`) reads raw Parquet, writes lossless event store → `data/consolidated/`
- **Viewpoints** (`datafactory_viewpoint`) reads consolidated store, writes materialized views → `data/viewpoint/`
- **Compilation** (`datafactory_compilation`) reads viewpoint Parquet, writes grid npy → `data/compiled/`
- **Assembly** (`scripts/assemble_grid.py`) combines compiled UCDP + static + admin → `data/assembled/`
- **Query** (`datafactory_query`) reads assembled grid (npy or zarr), provides `load_dataset()` API
- **Consumer bridge** (`scripts/generate_consumer_data.py`) translates factory → VIEWSER vocabulary
- Not all paths traverse all layers. Synthetic data reaches consumers directly (skips consolidation, viewpoint, and compilation).

## Package Layout

Multiple top-level packages under `src/` with `datafactory_` prefix:
- `datafactory_provenance` — content digests and JSONL ledger operations (Layer 0, no outbound imports)
- `datafactory_http` — HTTP request utilities: retry with exponential backoff (Layer 0, no outbound imports)
- `datafactory_priogrid` — PRIO-GRID spatial + temporal backbone (Layer 1, imports provenance + http)
- `datafactory_harvester` — data ingestion with pluggable sources: UCDP (annual, candidate, .9), PRIO-GRID static, GAUL admin boundaries (Layer 1, imports provenance + http)
- `datafactory_synthetic` — grid-native synthetic generation (Layer 1, imports provenance only)
- `datafactory_consolidation` — lossless consolidation of raw snapshots (Layer 2, imports provenance only)
- `datafactory_viewpoint` — opinionated, versioned views over consolidated data (Layer 3, imports provenance only)
- `datafactory_compilation` — viewpoint output → grid npy (Layer 4, imports provenance + priogrid)
- `datafactory_adapters` — consumer-facing conversions: grid → DataFrame, grid → FeatureFrame (no datafactory_* imports; sits alongside the graph, not inside it)
- `datafactory_query` — consumer entry point: `load_dataset()`, region/time/feature subsetting, dual npy/zarr backend (imports priogrid + adapters, reads assembled files)

## Tooling

- **Always use `uv run`** to invoke pytest, ruff, and scripts
- Build system: hatchling
- Linting: ruff (line-length 88)
- Type checking: mypy (strict)
- Testing: pytest

## Design Principles

1. **Graph, not pipeline** — sources don't know about consumers; not all paths traverse all layers
2. **Provenance all the way through** — every node writes JSONL ledger entries (mission-critical)
3. **Config-driven, fail-loud** — frozen dataclasses with `__post_init__` validation
4. **`__init__.py` always defines `__all__`** — public API is explicit
5. **npy now, zarr-ready contracts** — dimension order: (cells, time, features)
6. **No scope creep** — build only what's asked for; don't bolt on convenience features

## Strategic Documents

- `reports/rd_roadmap09.md` — R&D roadmap (ACLED Phase 2 complete, compilation decisions resolved, next: build compiler)
- `reports/product_development_plan09.md` — Product plan with v1.0/v1.1/v1.2/v2.0 gate criteria

## Vocabulary (aligned with Kleppmann & Riccomini, DDIA 2nd ed., 2026)

Our terminology maps to established data systems concepts:

- **Consolidated store** = system of record (Ch.1 pp.10-11) — the authoritative, lossless event store
- **Viewpoint** = materialized view / derived data (Ch.1 pp.35-36, Ch.12 pp.491-495) — opinionated, rebuildable from the consolidated store
- **Provenance ledger** = append-only audit log (Ch.1 p.10, Ch.11 p.457, Ch.12 p.495) — immutable record of every operation
- **Fail-loud** (ADR-011) = crash-stop fault model (Ch.2 pp.43-44, Ch.8 pp.274-276) — faults become visible failures, never hidden
- **Bounded staleness** (ADR-018) = SLO-based fault tolerance (Ch.2 pp.41-42, Ch.8 pp.237-240) — explicit freshness targets with operator judgment
- **Graph, not pipeline** (ADR-012) = ETL/ELT with multiple valid paths (Ch.1 pp.7-11, Ch.12 pp.499-501) — not all data traverses all layers
- **Immutable input** = batch processing principle (Ch.10 p.397) — raw snapshots never modified; outputs replace atomically
- **Schema evolution** = backward/forward compatibility (Ch.4 pp.112-127) — data outlives code; old and new formats must coexist
- **Idempotence** = exactly-once semantics via deduplication (Ch.12 pp.516-518) — safe to retry without side effects

## Relationship to views-metric-lab

The metric lab (`../views-metric-lab/`) is the first consumer. Grid and harvester code is being migrated from the lab into this repo. The lab retains models, metrics, losses, and evaluation infrastructure.
