# views-datafactory

Data factory for the VIEWS conflict forecasting platform.

## Architecture

The system is a **graph, not a pipeline** (ADR-012):
- **Source nodes** (`datafactory_harvester`, `datafactory_synthetic`) produce raw data independently
- **Consolidation** (`datafactory_consolidation`) combines raw vintages into lossless event stores
- **Viewpoints** (`datafactory_viewpoint`) apply opinionated rules to produce materialized views
- **Compilation** (`datafactory_compilation`) places viewpoint output onto the spatiotemporal grid
- **Consumer nodes** (metric lab, other VIEWS repos) read compiled outputs
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

- `reports/rd_roadmap02.md` — Research questions, hypotheses, data agenda, milestones
- `reports/product_development_plan02.md` — Users, requirements, architecture, release plan

## Relationship to views-metric-lab

The metric lab (`../views-metric-lab/`) is the first consumer. Grid and harvester code is being migrated from the lab into this repo. The lab retains models, metrics, losses, and evaluation infrastructure.
